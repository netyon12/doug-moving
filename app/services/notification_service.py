"""
Serviço de Notificações - DESATIVADO

Este serviço foi desativado. Todas as funções retornam sucesso silenciosamente
sem enviar notificações reais.

Autor: Manus AI
Data: 24 de Dezembro de 2025
Versão: 4.0 (DESATIVADO)
"""

import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Serviço de notificações DESATIVADO - Modo silencioso"""

    def __init__(self):
        """Inicializa o serviço em modo desativado"""
        self.enabled = False
        logger.info("ℹ️  Sistema de notificações DESATIVADO")

    def _enviar_template_whatsapp(self, telefone: str, template_name: str, parametros: list) -> bool:
        """
        Método desativado - retorna True sem enviar nada
        
        Args:
            telefone: Número do destinatário (ignorado)
            template_name: Nome do template (ignorado)
            parametros: Lista de parâmetros (ignorado)
            
        Returns:
            bool: Sempre True
        """
        return True

    def notificar_novas_viagens_em_lote(self, quantidade_viagens: int = 0) -> int:
        """
        Notificação desativada - retorna quantidade de viagens sem enviar nada
        
        Args:
            quantidade_viagens: Quantidade de viagens criadas
            
        Returns:
            int: Retorna a quantidade recebida (simula sucesso)
        """
        logger.debug(f"📭 Notificação desativada: {quantidade_viagens} viagem(ns) criada(s)")
        return quantidade_viagens

    def notificar_viagem_confirmada(self, viagem_id: int, motorista_id: int) -> dict:
        """
        Notificação desativada - retorna sucesso sem enviar nada
        
        Args:
            viagem_id: ID da viagem confirmada
            motorista_id: ID do motorista atribuído
            
        Returns:
            dict: {'success': True, 'enviadas': 1, 'falhas': 0}
        """
        logger.debug(f"📭 Notificação desativada: viagem {viagem_id} confirmada")
        return {
            'success': True,
            'enviadas': 1,
            'falhas': 0
        }

    def notificar_viagem_cancelada_colaboradores(self, viagem_id: int, motivo_cancelamento: str = '') -> dict:
        """
        Notificação desativada - retorna sucesso sem enviar nada
        
        Args:
            viagem_id: ID da viagem cancelada
            motivo_cancelamento: Motivo do cancelamento
            
        Returns:
            dict: {'success': True, 'enviadas': 1, 'falhas': 0}
        """
        logger.debug(f"📭 Notificação desativada: viagem {viagem_id} cancelada")
        return {
            'success': True,
            'enviadas': 1,
            'falhas': 0
        }

    def notificar_viagem_cancelada_por_motorista(self, viagem, motivo: str = '') -> int:
        """
        Notificação desativada - retorna 1 (sucesso) sem enviar nada
        
        Args:
            viagem: Objeto Viagem
            motivo: Motivo do cancelamento
            
        Returns:
            int: 1 (simula 1 notificação enviada)
        """
        logger.debug(f"📭 Notificação desativada: viagem {viagem.id} cancelada por motorista")
        return 1

    def notificar_viagem_iniciada(self, viagem_id: int, motorista_id: int) -> dict:
        """
        Notificação desativada - retorna sucesso sem enviar nada
        
        Args:
            viagem_id: ID da viagem iniciada
            motorista_id: ID do motorista
            
        Returns:
            dict: {'success': True, 'enviadas': 1, 'falhas': 0}
        """
        logger.debug(f"📭 Notificação desativada: viagem {viagem_id} iniciada")
        return {
            'success': True,
            'enviadas': 1,
            'falhas': 0
        }

    def notificar_viagem_finalizada(self, viagem_id: int, motorista_id: int) -> dict:
        """
        Notificação desativada - retorna sucesso sem enviar nada
        
        Args:
            viagem_id: ID da viagem finalizada
            motorista_id: ID do motorista
            
        Returns:
            dict: {'success': True, 'enviadas': 1, 'falhas': 0}
        """
        logger.debug(f"📭 Notificação desativada: viagem {viagem_id} finalizada")
        return {
            'success': True,
            'enviadas': 1,
            'falhas': 0
        }

    def notificar_colaborador_viagem_confirmada(self, colaborador_id: int, viagem_id: int) -> bool:
        """
        Notificação desativada - retorna True sem enviar nada
        
        Args:
            colaborador_id: ID do colaborador
            viagem_id: ID da viagem
            
        Returns:
            bool: True
        """
        logger.debug(f"📭 Notificação desativada: colaborador {colaborador_id} - viagem {viagem_id}")
        return True

    def notificar_motorista_nova_viagem(self, motorista_id: int, viagem_id: int) -> bool:
        """
        Notificação desativada - retorna True sem enviar nada
        
        Args:
            motorista_id: ID do motorista
            viagem_id: ID da viagem
            
        Returns:
            bool: True
        """
        logger.debug(f"📭 Notificação desativada: motorista {motorista_id} - viagem {viagem_id}")
        return True


# Instância global do serviço (em modo desativado)
notification_service = NotificationService()
