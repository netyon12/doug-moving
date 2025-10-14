"""
Serviço de Integração WhatsApp - Go Mobi
=========================================

Serviço para envio de notificações via WhatsApp usando Evolution API.

Autor: Manus AI
Data: 14 de outubro de 2025
Versão: 2.0
"""

import os
import requests
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# Configuração de logging
logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Serviço para envio de mensagens WhatsApp via Evolution API
    """
    
    def __init__(self):
        """
        Inicializa o serviço WhatsApp com configurações do ambiente
        """
        # Configurações da Evolution API
        self.api_url = os.getenv('EVOLUTION_API_URL', 'https://go-mobi-whatsapp.onrender.com')
        self.api_key = os.getenv('EVOLUTION_API_KEY', '')
        self.instance_name = os.getenv('EVOLUTION_INSTANCE_NAME', 'gomobi')
        
        # Configurações de comportamento
        self.enabled = os.getenv('WHATSAPP_ENABLED', 'true').lower() == 'true'
        self.send_notifications = os.getenv('WHATSAPP_SEND_NOTIFICATIONS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('WHATSAPP_TIMEOUT', '10'))
        self.country_code = os.getenv('WHATSAPP_COUNTRY_CODE', '55')
        
        # Headers para requisições
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': self.api_key
        }
        
        logger.info(f"WhatsAppService inicializado - Enabled: {self.enabled}, URL: {self.api_url}")
    
    def _format_phone(self, phone: str) -> str:
        """
        Formata o número de telefone para o padrão internacional
        
        Args:
            phone: Número de telefone (pode ter DDD, espaços, etc)
        
        Returns:
            Número formatado no padrão: 5511999999999
        """
        if not phone:
            return ""
        
        # Remove caracteres não numéricos
        phone = ''.join(filter(str.isdigit, phone))
        
        # Se não tem código do país, adiciona
        if not phone.startswith(self.country_code):
            phone = self.country_code + phone
        
        return phone
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Faz uma requisição para a Evolution API
        
        Args:
            endpoint: Endpoint da API (ex: '/message/sendText')
            data: Dados a serem enviados
        
        Returns:
            Resposta da API ou None em caso de erro
        """
        if not self.enabled:
            logger.warning("WhatsApp está desabilitado. Configure WHATSAPP_ENABLED=true")
            return None
        
        if not self.api_key:
            logger.error("EVOLUTION_API_KEY não configurada")
            return None
        
        url = f"{self.api_url}{endpoint}/{self.instance_name}"
        
        try:
            response = requests.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Mensagem enviada com sucesso para {data.get('number', 'N/A')}")
                return response.json()
            else:
                logger.error(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return None
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao enviar mensagem para {data.get('number', 'N/A')}")
            return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição: {e}")
            return None
    
    def send_message(self, phone: str, message: str) -> bool:
        """
        Envia uma mensagem de texto simples
        
        Args:
            phone: Número de telefone do destinatário
            message: Texto da mensagem
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.enabled or not self.send_notifications:
            logger.info("Envio de notificações desabilitado")
            return False
        
        phone_formatted = self._format_phone(phone)
        
        if not phone_formatted:
            logger.warning(f"Telefone inválido: {phone}")
            return False
        
        data = {
            "number": phone_formatted,
            "textMessage": {
                "text": message
            }
        }
        
        result = self._make_request('/message/sendText', data)
        return result is not None
    
    def check_connection(self) -> bool:
        """
        Verifica se a instância do WhatsApp está conectada
        
        Returns:
            True se conectado, False caso contrário
        """
        if not self.enabled:
            return False
        
        url = f"{self.api_url}/instance/connectionState/{self.instance_name}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                state = data.get('instance', {}).get('state', '')
                is_connected = state == 'open'
                
                logger.info(f"Status da conexão WhatsApp: {state}")
                return is_connected
            else:
                logger.error(f"Erro ao verificar conexão: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao verificar conexão: {e}")
            return False
    
    def send_notification_viagem_aceita(self, viagem) -> int:
        """
        Envia notificação para colaboradores quando motorista aceita a viagem
        
        Template da mensagem:
        🚗 Sua Viagem Foi Agendada!
        
        Olá [Nome do Colaborador],
        
        Sua viagem está a caminho:
        
        🚙 Informações do Motorista
        • Nome: [Nome]
        • Veículo: [Modelo]
        • Placa: [Placa]
        • Cor: [Cor]
        
        📍 Detalhes da Viagem
        • Tipo: [Entrada/Saída]
        • Horário: [HH:MM]
        
        Por favor, aguarde no ponto de embarque.
        
        Args:
            viagem: Objeto Viagem do banco de dados
        
        Returns:
            Número de mensagens enviadas com sucesso
        """
        if not self.enabled or not self.send_notifications:
            logger.info("Notificações WhatsApp desabilitadas")
            return 0
        
        if not viagem.motorista:
            logger.warning(f"Viagem {viagem.id} não tem motorista atribuído")
            return 0
        
        motorista = viagem.motorista
        enviadas = 0
        
        # Dados do motorista
        motorista_nome = motorista.nome or "Não informado"
        veiculo_nome = motorista.veiculo_nome or "Não informado"
        veiculo_placa = motorista.veiculo_placa or "Não informada"
        veiculo_cor = motorista.veiculo_cor or "Não informada"
        
        # Dados da viagem
        tipo_viagem = viagem.tipo_corrida or "Não informado"
        
        # Formata horário
        if viagem.data_inicio:
            horario = viagem.data_inicio.strftime('%H:%M')
        else:
            horario = "Não informado"
        
        # Busca todos os colaboradores da viagem
        solicitacoes = viagem.solicitacoes
        
        if not solicitacoes:
            logger.warning(f"Viagem {viagem.id} não tem solicitações/colaboradores")
            return 0
        
        # Envia para cada colaborador
        for solicitacao in solicitacoes:
            colaborador = solicitacao.colaborador
            
            if not colaborador:
                continue
            
            if not colaborador.telefone:
                logger.warning(f"Colaborador {colaborador.nome} não tem telefone cadastrado")
                continue
            
            # Monta a mensagem personalizada
            mensagem = f"""🚗 *Sua Viagem Foi Agendada!*

Olá {colaborador.nome},

Sua viagem está a caminho:

🚙 *Informações do Motorista*
• Nome: {motorista_nome}
• Veículo: {veiculo_nome}
• Placa: {veiculo_placa}
• Cor: {veiculo_cor}

📍 *Detalhes da Viagem*
• Tipo: {tipo_viagem}
• Horário: {horario}

Por favor, aguarde no ponto de embarque.

_Mensagem automática do Go Mobi_"""
            
            # Envia a mensagem
            if self.send_message(colaborador.telefone, mensagem):
                enviadas += 1
                logger.info(f"Notificação enviada para {colaborador.nome} ({colaborador.telefone})")
            else:
                logger.error(f"Falha ao enviar notificação para {colaborador.nome}")
        
        logger.info(f"Total de notificações enviadas para viagem {viagem.id}: {enviadas}")
        return enviadas
    
    def send_notification_viagem_criada(self, viagem) -> bool:
        """
        Envia notificação para motorista quando uma viagem é criada/atribuída
        
        Args:
            viagem: Objeto Viagem do banco de dados
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.enabled or not self.send_notifications:
            return False
        
        if not viagem.motorista:
            logger.warning(f"Viagem {viagem.id} não tem motorista atribuído")
            return False
        
        motorista = viagem.motorista
        
        if not motorista.telefone:
            logger.warning(f"Motorista {motorista.nome} não tem telefone cadastrado")
            return False
        
        # Conta colaboradores
        num_passageiros = len(viagem.solicitacoes) if viagem.solicitacoes else 0
        
        # Formata data
        if viagem.data_inicio:
            data_formatada = viagem.data_inicio.strftime('%d/%m/%Y às %H:%M')
        else:
            data_formatada = "Não informada"
        
        # Calcula valor do repasse (se disponível)
        valor_repasse = viagem.valor_repasse if hasattr(viagem, 'valor_repasse') and viagem.valor_repasse else 0
        
        mensagem = f"""🚗 *Nova Viagem Atribuída!*

Olá {motorista.nome},

Uma nova viagem foi atribuída a você:

📋 *Detalhes da Viagem*
• ID: #{viagem.id}
• Data: {data_formatada}
• Tipo: {viagem.tipo_corrida or 'Não informado'}
• Passageiros: {num_passageiros}
• Valor Repasse: R$ {valor_repasse:.2f}

Acesse o sistema para mais detalhes.

_Mensagem automática do Go Mobi_"""
        
        result = self.send_message(motorista.telefone, mensagem)
        
        if result:
            logger.info(f"Motorista {motorista.nome} notificado sobre viagem {viagem.id}")
        
        return result
    
    def send_notification_viagem_finalizada(self, viagem) -> bool:
        """
        Envia notificação para motorista quando uma viagem é finalizada
        
        Args:
            viagem: Objeto Viagem do banco de dados
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.enabled or not self.send_notifications:
            return False
        
        if not viagem.motorista:
            logger.warning(f"Viagem {viagem.id} não tem motorista")
            return False
        
        motorista = viagem.motorista
        
        if not motorista.telefone:
            logger.warning(f"Motorista {motorista.nome} não tem telefone cadastrado")
            return False
        
        # Conta colaboradores
        num_passageiros = len(viagem.solicitacoes) if viagem.solicitacoes else 0
        
        # Formata datas
        if viagem.data_inicio:
            data_inicio = viagem.data_inicio.strftime('%d/%m/%Y %H:%M')
        else:
            data_inicio = "N/A"
        
        if viagem.data_finalizacao:
            data_fim = viagem.data_finalizacao.strftime('%d/%m/%Y %H:%M')
        else:
            data_fim = "N/A"
        
        # Valor do repasse
        valor_repasse = viagem.valor_repasse if hasattr(viagem, 'valor_repasse') and viagem.valor_repasse else 0
        
        mensagem = f"""✅ *Viagem Finalizada com Sucesso!*

Olá {motorista.nome},

Sua viagem foi finalizada:

📋 *Resumo da Viagem*
• ID: #{viagem.id}
• Tipo: {viagem.tipo.corrida or 'N/A'}
• Início: {data_inicio}
• Fim: {data_fim}
• Passageiros: {num_passageiros}

💰 *Valor do Repasse*
• R$ {valor_repasse:.2f}

Obrigado pelo excelente trabalho!

_Mensagem automática do Go Mobi_"""
        
        result = self.send_message(motorista.telefone, mensagem)
        
        if result:
            logger.info(f"Motorista {motorista.nome} notificado sobre finalização da viagem {viagem.id}")
        
        return result
    
    def send_notification_solicitacao_aprovada(self, solicitacao) -> bool:
        """
        Envia notificação para colaborador quando solicitação é aprovada
        
        Args:
            solicitacao: Objeto Solicitacao do banco de dados
        
        Returns:
            True se enviado com sucesso, False caso contrário
        """
        if not self.enabled or not self.send_notifications:
            return False
        
        colaborador = solicitacao.colaborador
        
        if not colaborador:
            logger.warning(f"Solicitação {solicitacao.id} não tem colaborador")
            return False
        
        if not colaborador.telefone:
            logger.warning(f"Colaborador {colaborador.nome} não tem telefone cadastrado")
            return False
        
        # Formata data
        if solicitacao.data_solicitacao:
            data_formatada = solicitacao.data_solicitacao.strftime('%d/%m/%Y')
        else:
            data_formatada = "N/A"
        
        mensagem = f"""✅ *Solicitação Aprovada!*

Olá {colaborador.nome},

Sua solicitação de transporte foi aprovada:

📋 *Detalhes*
• Data: {data_formatada}
• Tipo: {solicitacao.tipo or 'N/A'}
• Status: Aprovada

Em breve você receberá informações sobre o motorista.

_Mensagem automática do Go Mobi_"""
        
        result = self.send_message(colaborador.telefone, mensagem)
        
        if result:
            logger.info(f"Colaborador {colaborador.nome} notificado sobre aprovação da solicitação {solicitacao.id}")
        
        return result


# Instância global do serviço
whatsapp_service = WhatsAppService()