"""
===================================================
Serviço de Notificações WhatsApp via Evolution API
===================================================

⚠️ SERVIÇO DESATIVADO ⚠️

Este serviço está temporariamente DESATIVADO devido ao bloqueio
da conta WhatsApp Business pela Meta.

Motivo: Atividade recente não segue os Termos de Serviço do WhatsApp Business
Data de desativação: 26 de Novembro de 2025

Para reativar:
1. Resolver problema com Meta/WhatsApp Business
2. Alterar no .env: WHATSAPP_ENABLED=true
3. Configurar credenciais da Evolution API
4. Testar conexão antes de usar em produção

Autor: Manus AI
Versão: v6 DESATIVADO
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configuração de logging
logger = logging.getLogger(__name__)


class WhatsAppServiceEvolution:
    """Serviço para envio de mensagens WhatsApp via Evolution API - DESATIVADO"""

    def __init__(self):
        """Inicializa o serviço (DESATIVADO)"""
        # Configurações mantidas para futura reativação
        self.api_url = os.getenv('EVOLUTION_API_URL', '')
        self.api_key = os.getenv('EVOLUTION_API_KEY', '')
        self.instance_name = os.getenv('EVOLUTION_INSTANCE_NAME', 'gomobi')
        self.phone_number = os.getenv('WHATSAPP_PHONE_NUMBER', '')

        # SERVIÇO DESATIVADO
        self.enabled = False  # Forçado como False
        self.send_notifications = False  # Forçado como False

        self.timeout = int(os.getenv('WHATSAPP_TIMEOUT', '120'))
        self.grupo_motoristas_id = os.getenv(
            'WHATSAPP_GRUPO_MOTORISTAS_ID', '')

        # Headers para requisições (mantidos para futura reativação)
        self.headers = {
            'apikey': self.api_key,
            'Content-Type': 'application/json'
        }

        # Log de aviso
        logger.warning(
            "⚠️ WhatsApp Service DESATIVADO - Conta bloqueada pela Meta")

    def _servico_desativado(self, funcao_nome: str) -> Dict[str, Any]:
        """Retorna mensagem padrão de serviço desativado"""
        mensagem = (
            f"WhatsApp Service DESATIVADO - Função '{funcao_nome}' não executada. "
            f"Motivo: Conta WhatsApp Business bloqueada pela Meta. "
            f"Para reativar, resolva o problema com a Meta e configure WHATSAPP_ENABLED=true no .env"
        )
        logger.warning(mensagem)
        return {
            'success': False,
            'disabled': True,
            'reason': 'whatsapp_blocked_by_meta',
            'message': mensagem,
            'timestamp': datetime.now().isoformat()
        }

    def verificar_conexao(self) -> Dict[str, Any]:
        """Verifica conexão com Evolution API - DESATIVADO"""
        return self._servico_desativado('verificar_conexao')

    def listar_grupos(
        self,
        get_participants: bool = True,
        max_retries: int = 3,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Lista todos os grupos do WhatsApp - DESATIVADO"""
        return self._servico_desativado('listar_grupos')

    def _send_group_message(
        self,
        group_id: str,
        message: str,
        max_retries: int = 3,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Envia mensagem para um grupo - DESATIVADO"""
        return self._servico_desativado('_send_group_message')

    def _send_individual_message(
        self,
        phone_number: str,
        message: str
    ) -> Dict[str, Any]:
        """Envia mensagem para um número individual - DESATIVADO"""
        return self._servico_desativado('_send_individual_message')

    def notificar_nova_viagem_motorista(
        self,
        motorista_telefone: str,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica motorista sobre nova viagem - DESATIVADO"""
        return self._servico_desativado('notificar_nova_viagem_motorista')

    def notificar_nova_viagem_grupo_motoristas(
        self,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica grupo de motoristas sobre nova viagem - DESATIVADO"""
        return self._servico_desativado('notificar_nova_viagem_grupo_motoristas')

    def notificar_novas_viagens_grupo_motoristas(
        self,
        viagens: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Notifica grupo de motoristas sobre múltiplas viagens - DESATIVADO"""
        return self._servico_desativado('notificar_novas_viagens_grupo_motoristas')

    def notificar_viagem_confirmada_motorista(
        self,
        motorista_telefone: str,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica motorista sobre viagem confirmada - DESATIVADO"""
        return self._servico_desativado('notificar_viagem_confirmada_motorista')

    def notificar_viagem_cancelada_motorista(
        self,
        motorista_telefone: str,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica motorista sobre viagem cancelada - DESATIVADO"""
        return self._servico_desativado('notificar_viagem_cancelada_motorista')

    def notificar_viagem_confirmada_colaborador(
        self,
        colaborador_telefone: str,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica colaborador sobre viagem confirmada - DESATIVADO"""
        return self._servico_desativado('notificar_viagem_confirmada_colaborador')

    def notificar_viagem_cancelada_colaborador(
        self,
        colaborador_telefone: str,
        viagem_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Notifica colaborador sobre viagem cancelada - DESATIVADO"""
        return self._servico_desativado('notificar_viagem_cancelada_colaborador')


# Instância global do serviço (DESATIVADO) - Ativar ou desativar integração com Whatsapp. Ativar = retirar comentário abaixo.
whatsapp_service = WhatsAppServiceEvolution()


# Funções de integração com o sistema (TODAS DESATIVADAS)
def notificar_nova_viagem_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica motorista sobre nova viagem - DESATIVADO"""
    return whatsapp_service.notificar_nova_viagem_motorista(motorista_telefone, viagem_info)


def notificar_nova_viagem_grupo_motoristas(viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica grupo de motoristas sobre nova viagem - DESATIVADO"""
    return whatsapp_service.notificar_nova_viagem_grupo_motoristas(viagem_info)


def notificar_novas_viagens_grupo_motoristas(viagens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Notifica grupo de motoristas sobre múltiplas viagens - DESATIVADO"""
    return whatsapp_service.notificar_novas_viagens_grupo_motoristas(viagens)


def notificar_viagem_confirmada_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica motorista sobre viagem confirmada - DESATIVADO"""
    return whatsapp_service.notificar_viagem_confirmada_motorista(motorista_telefone, viagem_info)


def notificar_viagem_cancelada_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica motorista sobre viagem cancelada - DESATIVADO"""
    return whatsapp_service.notificar_viagem_cancelada_motorista(motorista_telefone, viagem_info)


def notificar_viagem_confirmada_colaborador(colaborador_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica colaborador sobre viagem confirmada - DESATIVADO"""
    return whatsapp_service.notificar_viagem_confirmada_colaborador(colaborador_telefone, viagem_info)


def notificar_viagem_cancelada_colaborador(colaborador_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
    """Notifica colaborador sobre viagem cancelada - DESATIVADO"""
    return whatsapp_service.notificar_viagem_cancelada_colaborador(colaborador_telefone, viagem_info)
