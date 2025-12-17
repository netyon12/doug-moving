"""
Configuração da Meta Cloud API para WhatsApp
=============================================

Este módulo contém as configurações necessárias para integração
com a Meta Cloud API (WhatsApp Business API Oficial).

IMPORTANTE: Substitua os valores abaixo com suas credenciais reais!

# ID do Aplicativo
APP_ID=856538507052482

# Token de Acesso (este é temporário!)
ACCESS_TOKEN=EAAMLBGlzBcIBP0nS0zEu2BLIsktZAqs02mG8dcSZBQNYSDlropu5QKfm8wdmznHrkIWAuJyJNLQh57

# Phone Number ID
PHONE_NUMBER_ID=786447364561104

# WhatsApp Business Account ID
WABA_ID=121200658743632

"""

import os

# ============================================
# META CLOUD API - CONFIGURAÇÕES OFICIAIS
# ============================================

# Access Token gerado no painel da Meta
# Obtenha em: https://developers.facebook.com/ → Seu App → WhatsApp → API Setup
WHATSAPP_META_ACCESS_TOKEN = os.getenv(
    'WHATSAPP_META_ACCESS_TOKEN',
    ''  # ⚠️ CONFIGURE ESTA VARIÁVEL DE AMBIENTE!
)

# ID do número de telefone do WhatsApp Business
# Encontre em: https://developers.facebook.com/ → Seu App → WhatsApp → API Setup
WHATSAPP_META_PHONE_NUMBER_ID = os.getenv(
    'WHATSAPP_META_PHONE_NUMBER_ID',
    ''  # ⚠️ CONFIGURE ESTA VARIÁVEL DE AMBIENTE!
)

# Versão da API do WhatsApp (não altere a menos que saiba o que está fazendo)
WHATSAPP_META_API_VERSION = os.getenv('WHATSAPP_META_API_VERSION', 'v21.0')

# ============================================
# CONFIGURAÇÕES GERAIS
# ============================================

# Habilitar/Desabilitar WhatsApp
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() == 'true'

# Habilitar/Desabilitar notificações automáticas
WHATSAPP_SEND_NOTIFICATIONS = os.getenv(
    'WHATSAPP_SEND_NOTIFICATIONS', 'true').lower() == 'true'

# Timeout para requisições (em segundos)
WHATSAPP_TIMEOUT = int(os.getenv('WHATSAPP_TIMEOUT', '10'))

# Prefixo do país (Brasil)
WHATSAPP_COUNTRY_CODE = os.getenv('WHATSAPP_COUNTRY_CODE', '55')

# Intervalo entre mensagens (em segundos) para evitar bloqueio
WHATSAPP_MESSAGE_INTERVAL = int(os.getenv('WHATSAPP_MESSAGE_INTERVAL', '3'))

# ============================================
# VALIDAÇÃO DE CONFIGURAÇÃO
# ============================================


def validar_configuracao():
    """
    Valida se as configurações necessárias estão presentes

    Returns:
        tuple: (is_valid, error_message)
    """
    if not WHATSAPP_ENABLED:
        return (True, "WhatsApp desabilitado")

    if not WHATSAPP_META_ACCESS_TOKEN:
        return (False, "WHATSAPP_META_ACCESS_TOKEN não configurado!")

    if not WHATSAPP_META_PHONE_NUMBER_ID:
        return (False, "WHATSAPP_META_PHONE_NUMBER_ID não configurado!")

    return (True, "Configuração OK")


# Validação automática ao importar
if __name__ != '__main__':
    is_valid, message = validar_configuracao()
    if not is_valid:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ Configuração WhatsApp: {message}")
