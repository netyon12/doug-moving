from typing import Dict, Any, List
from datetime import datetime
from app.services.evolution_api import WhatsAppServiceEvolution

# --- Funções de serviço de notificação ---

def _servico_desativado(funcao: str) -> Dict[str, Any]:
    """Retorna um dicionário indicando que o serviço de WhatsApp está desativado."""
    return {
        "status": "desativado",
        "mensagem": f"Serviço de WhatsApp desativado. Função '{funcao}' não executada.",
        "timestamp": datetime.now().isoformat()
    }

# --- Funções de notificação (Comentadas para desativação completa) ---

# # Instância global do serviço (DESATIVADO) - Ativar ou desativar integração com Whatsapp. Ativar = retirar comentário abaixo.
# whatsapp_service = WhatsAppServiceEvolution()


# # Funções de integração com o sistema (TODAS DESATIVADAS)
# def notificar_nova_viagem_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica motorista sobre nova viagem - DESATIVADO"""
#     return whatsapp_service.notificar_nova_viagem_motorista(motorista_telefone, viagem_info)


# def notificar_nova_viagem_grupo_motoristas(viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica grupo de motoristas sobre nova viagem - DESATIVADO"""
#     return whatsapp_service.notificar_nova_viagem_grupo_motoristas(viagem_info)


# def notificar_novas_viagens_grupo_motoristas(viagens: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """Notifica grupo de motoristas sobre múltiplas viagens - DESATIVADO"""
#     return whatsapp_service.notificar_novas_viagens_grupo_motoristas(viagens)


# def notificar_viagem_confirmada_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica motorista sobre viagem confirmada - DESATIVADO"""
#     return whatsapp_service.notificar_viagem_confirmada_motorista(motorista_telefone, viagem_info)


# def notificar_viagem_cancelada_motorista(motorista_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica motorista sobre viagem cancelada - DESATIVADO"""
#     return whatsapp_service.notificar_viagem_cancelada_motorista(motorista_telefone, viagem_info)


# def notificar_viagem_confirmada_colaborador(colaborador_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica colaborador sobre viagem confirmada - DESATIVADO"""
#     return whatsapp_service.notificar_viagem_confirmada_colaborador(colaborador_telefone, viagem_info)


# def notificar_viagem_cancelada_colaborador(colaborador_telefone: str, viagem_info: Dict[str, Any]) -> Dict[str, Any]:
#     """Notifica colaborador sobre viagem cancelada - DESATIVADO"""
#     return whatsapp_service.notificar_viagem_cancelada_colaborador(colaborador_telefone, viagem_info)
