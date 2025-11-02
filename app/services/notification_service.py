"""
Serviço de Notificações - Go Mobi
==================================

Gerencia envio de notificações por WhatsApp para diferentes situações.

Autor: Manus AI
Data: 16 de outubro de 2025
Versão: 1.0
"""

import logging
from typing import List
from datetime import datetime
from app.models import Motorista, Viagem, Colaborador
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Serviço para gerenciar notificações do sistema
    """
    
    def __init__(self):
        self.whatsapp = whatsapp_service
    
    def notificar_viagem_disponivel(self, viagem: Viagem) -> int:
        """
        Notifica todos os motoristas disponíveis sobre nova viagem
        
        Args:
            viagem: Objeto Viagem recém-criada
        
        Returns:
            Número de notificações enviadas com sucesso
        """
        # Busca motoristas disponíveis (status Ativo ou Disponível)
        motoristas = Motorista.query.filter(
            Motorista.status.in_(['Ativo', 'Disponível'])
        ).all()
        
        if not motoristas:
            logger.warning("Nenhum motorista disponível encontrado")
            return 0
        
        # Prepara dados da viagem
        viagem_id = viagem.id
        
        # Coleta blocos da viagem
        if viagem.blocos_ids:
            # Se tem múltiplos blocos
            blocos_lista = []
            blocos_ids = [int(x.strip()) for x in viagem.blocos_ids.split(',') if x.strip()]
            from app.models import Bloco
            blocos_objs = Bloco.query.filter(Bloco.id.in_(blocos_ids)).all()
            blocos_lista = [b.codigo_bloco for b in blocos_objs]
            blocos_texto = ', '.join(blocos_lista) if blocos_lista else 'N/A'
        elif viagem.bloco:
            # Se tem apenas um bloco
            blocos_texto = viagem.bloco.codigo_bloco
        else:
            blocos_texto = 'N/A'
        
        quantidade_passageiros = viagem.quantidade_passageiros or 0
        
        # Formata valor do repasse (o que o motorista recebe)
        if viagem.valor_repasse:  # ✅ Valor que o motorista recebe
            valor_texto = f"R$ {float(viagem.valor_repasse):.2f}".replace('.', ',')
        else:
            valor_texto = 'Não informado'
        
        # Template da mensagem
        template = """🚗 *Nova Viagem Disponível!*
Olá {motorista_nome},

Nova Viagem disponível no aplicativo Go Mobi! *[ID Viagem: {viagem_id}]*
Acesse a plataforma para agendar sua corrida com o colaborador!
*Blocos da Viagem:* {blocos}
*Nro de Passageiros:* {passageiros}
*Valor do Repasse:* {valor}

Acesse a Go Mobi: https://doug-moving.onrender.com/"""
        
        enviadas = 0
        
        for motorista in motoristas:
            if not motorista.telefone:
                logger.warning(f"Motorista {motorista.nome} sem telefone cadastrado")
                continue
            
            # Gera mensagem personalizada
            mensagem = template.format(
                motorista_nome=motorista.nome,
                viagem_id=viagem_id,
                blocos=blocos_texto,
                passageiros=quantidade_passageiros,
                valor=valor_texto
            )
            
            # Envia WhatsApp
            try:
                if self.whatsapp.send_message(motorista.telefone, mensagem):
                    enviadas += 1
                    logger.info(f"Notificação enviada para motorista {motorista.nome}")
            except Exception as e:
                logger.error(f"Erro ao enviar notificação para {motorista.nome}: {e}")
        
        logger.info(f"Notificações de viagem disponível enviadas: {enviadas}/{len(motoristas)}")
        return enviadas
    
    def notificar_viagem_cancelada_por_motorista(self, viagem: Viagem, motivo: str = None) -> int:
        """
        Notifica colaboradores sobre cancelamento de viagem pelo motorista
        
        Args:
            viagem: Objeto Viagem cancelada
            motivo: Motivo do cancelamento (opcional)
        
        Returns:
            Número de notificações enviadas com sucesso
        """
        # Busca colaboradores da viagem
        solicitacoes = viagem.solicitacoes
        
        if not solicitacoes:
            logger.warning(f"Viagem {viagem.id} não tem solicitações/colaboradores")
            return 0
        
        # Prepara dados da viagem
        viagem_id = viagem.id
        
        # Template da mensagem
        template = """❌ *Viagem Cancelada*
Olá {colaborador_nome},

Sua viagem de ID *{viagem_id}* foi cancelada!
Mas não se preocupe! Sua viagem já está disponível para outros motoristas agendarem.
Assim que um novo motorista agendar, chegará a confirmação."""
        
        enviadas = 0
        
        for solicitacao in solicitacoes:
            colaborador = solicitacao.colaborador
            
            if not colaborador or not colaborador.telefone:
                logger.warning(f"Colaborador sem telefone na solicitação {solicitacao.id}")
                continue
            
            # Gera mensagem personalizada
            mensagem = template.format(
                colaborador_nome=colaborador.nome,
                viagem_id=viagem_id
            )
            
            # Envia WhatsApp
            try:
                if self.whatsapp.send_message(colaborador.telefone, mensagem):
                    enviadas += 1
                    logger.info(f"Notificação enviada para colaborador {colaborador.nome}")
            except Exception as e:
                logger.error(f"Erro ao enviar notificação para {colaborador.nome}: {e}")
        
        logger.info(f"Notificações de viagem cancelada enviadas: {enviadas}/{len(solicitacoes)}")
        return enviadas


# Instância global
notification_service = NotificationService()

