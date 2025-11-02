"""
Configuração da Evolution API para WhatsApp
============================================

Este módulo contém as configurações necessárias para integração
com a Evolution API do WhatsApp.
"""

import os

# URL da Evolution API no Render
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', 'https://go-mobi-whatsapp.onrender.com')

# Chave de API para autenticação
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY', '')

# Nome da instância do WhatsApp
EVOLUTION_INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE_NAME', 'gomobi')

# Habilitar/Desabilitar WhatsApp
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() == 'true'

# Habilitar/Desabilitar notificações automáticas
WHATSAPP_SEND_NOTIFICATIONS = os.getenv('WHATSAPP_SEND_NOTIFICATIONS', 'true').lower() == 'true'

# Timeout para requisições (em segundos)
WHATSAPP_TIMEOUT = int(os.getenv('WHATSAPP_TIMEOUT', '10'))

# Prefixo do país (Brasil)
WHATSAPP_COUNTRY_CODE = os.getenv('WHATSAPP_COUNTRY_CODE', '55')

