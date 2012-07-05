# -*- encoding: utf8 -*-

import importlib
from datetime import datetime
from cnab240 import errors


class Evento(object):

    def __init__(self, banco, codigo_evento):
        self._segmentos = []
        self.banco = banco 
        self.codigo_evento = codigo_evento
        self._codigo_lote = None
        
    def adicionar_segmento(self, segmento):
        self._segmentos.append(segmento) 
        for segmento in self._segmentos:
            segmento.servico_codigo_movimento = self.codigo_evento
 
    @property
    def segmentos(self):    
        return self._segmentos
    
    def __getattribute__(self, name):
        for segmento in object.__getattribute__(self, '_segmentos'):
            if hasattr(segmento, name):
                return getattr(segmento, name)
        return object.__getattribute__(self, name)
    
    def __unicode__(self):
        return u'\r\n'.join(unicode(seg) for seg in self._segmentos)

    def __len__(self):
        return len(self._segmentos)

    @property
    def codigo_lote(self):
        return self._codigo_lote

    @codigo_lote.setter
    def codigo_lote(self, valor):
        self._codigo_lote = valor
        for segmento in self._segmentos:
            segmento.controle_lote = valor  
    
    def atualizar_codigo_registros(self, last_id):
        current_id = last_id 
        for segmento in self._segmentos:
            current_id += 1
            segmento.servico_numero_registro = current_id
        return current_id

class Lote(object):

    def __init__(self, banco, header=None, trailer=None):
        self.banco = banco
        self.header = header
        self.trailer = trailer 
        self._codigo = None
        self.trailer.quantidade_registros = 2
        self._eventos = [] 

    @property
    def codigo(self):
        return self._codigo   

    @codigo.setter
    def codigo(self, valor):
        self._codigo = valor
        self.header.controle_lote = valor
        self.trailer.controle_lote = valor
        self.atualizar_codigo_eventos()

    def atualizar_codigo_eventos(self):
        for evento in self._eventos:
            evento.codigo_lote = self._codigo

    def atualizar_codigo_registros(self):
        last_id = 0
        for evento in self._eventos:       
             last_id = evento.atualizar_codigo_registros(last_id) 
 
    @property
    def eventos(self):
        return self._eventos   
 
    def adicionar_evento(self, evento):
        if not isinstance(evento, Evento):
            raise TypeError

        self._eventos.append(evento)
        self.trailer.quantidade_registros += len(evento)
        self.atualizar_codigo_registros()        
        
        if self._codigo:
            self.atualizar_codigo_eventos()

    def __unicode__(self):
        if not self._eventos:
            raise errors.NenhumEventoError()
    
        result = [] 
        result.append(unicode(self.header))
        result.extend(unicode(evento) for evento in self._eventos)
        result.append(unicode(self.trailer))
        return '\r\n'.join(result)

    def __len__(self):
        return self.trailer.quantidade_registros


class Arquivo(object):

    def __init__(self, banco, **kwargs):
        """Arquivo Cnab240.""" 

        self._lotes = []
        self.banco = banco
      
        self.header = self.banco.registros.HeaderArquivo(**kwargs) 
        self.trailer = self.banco.registros.TrailerArquivo(**kwargs)
        self.trailer.totais_quantidade_lotes = 0        
        self.trailer.totais_quantidade_registros = 2

        if self.header.arquivo_data_de_geracao is None:
            now = datetime.now()
            self.header.arquivo_data_de_geracao = int(now.strftime("%d%m%Y"))

        if self.header.arquivo_hora_de_geracao is None:
            if now is None:
                now = datetime.now()
            self.header.arquivo_hora_de_geracao = int(now.strftime("%H%M%S"))
        
    @property
    def lotes(self):
        return self._lotes

    def incluir_cobranca(self, **kwargs):
        codigo_evento = 1
        evento = Evento(self.banco, codigo_evento) 
            
        seg_p = self.banco.registros.SegmentoP(**kwargs)
        evento.adicionar_segmento(seg_p)
            
        seg_q = self.banco.registros.SegmentoQ(**kwargs)
        evento.adicionar_segmento(seg_q)
        
        seg_r = self.banco.registros.SegmentoR(**kwargs)
        if seg_r.necessario():
            evento.adicionar_segmento(seg_r)

        # 1 eh o codigo de cobranca
        lote_cobranca = self.encontrar_lote(codigo_evento)
        
        if lote_cobranca is None:
            header = self.banco.registros.HeaderLoteCobranca(**self.header.todict())
            trailer = self.banco.registros.TrailerLoteCobranca()
            lote_cobranca = Lote(self.banco, header, trailer) 
            self.adicionar_lote(lote_cobranca)

            if header.controlecob_numero is None:
                controlecob_numero = str(self.header.arquivo_sequencia).lstrip('0')
                controlecob_numero += str(lote_cobranca.codigo).lstrip('0')
                header.controlecob_numero = int(controlecob_numero)

            if header.controlecob_data_gravacao is None:
                header.controlecob_data_gravacao = self.header.arquivo_data_de_geracao
   
        lote_cobranca.adicionar_evento(evento)
 
    def encontrar_lote(self, codigo_servico):
        for lote in self.lotes:
            if lote.header.servico_servico == codigo_servico:
                return lote
 
    def adicionar_lote(self, lote):
        if not isinstance(lote, Lote):
            raise TypeError('Objeto deve ser instancia de "Lote"')

        self._lotes.append(lote)
        lote.codigo = len(self._lotes)

        # Incrementar numero de lotes no trailer do arquivo
        self.trailer.totais_quantidade_lotes += 1

        # Incrementar numero de registros no trailer do arquivo
        self.trailer.totais_quantidade_registros += len(lote)

    def escrever(self, file_):
        file_.write(unicode(self.encode('ascii')))

    def __unicode__(self):
        if not self._lotes:
            raise errors.ArquivoVazioError()
        
        result = []
        result.append(unicode(self.header))
        result.extend(unicode(lote) for lote in self._lotes)
        result.append(unicode(self.trailer))
        return u'\n'.join(result)

