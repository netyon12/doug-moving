"""
Serviço de Integração WhatsApp - Go Mobi
=========================================

Serviço para envio de notificações via WhatsApp usando Evolution API.

Autor: Manus AI
Data: 14 de outubro de 2025
Versão: 2.1 - CORRIGIDO
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
    
    def _get_tipo_viagem_formatado(self, viagem) -> str:
        """
        Formata o tipo da viagem de forma legível
        
        Args:
            viagem: Objeto Viagem
            
        Returns:
            String formatada com tipo da viagem
        """
        tipo_linha = viagem.tipo_linha if hasattr(viagem, 'tipo_linha') else None
        tipo_corrida = viagem.tipo_corrida if hasattr(viagem, 'tipo_corrida') else None
        
        # Formata tipo_linha
        linha_texto = ""
        if tipo_linha == 'FIXA':
            linha_texto = "Linha Fixa"
        elif tipo_linha == 'EXTRA':
            linha_texto = "Linha Extra"
        else:
            linha_texto = tipo_linha or "Não informado"
        
        # Formata tipo_corrida
        corrida_texto = ""
        if tipo_corrida == 'entrada':
            corrida_texto = "Entrada"
        elif tipo_corrida == 'saida':
            corrida_texto = "Saída"
        elif tipo_corrida == 'entrada_saida':
            corrida_texto = "Entrada e Saída"
        elif tipo_corrida == 'desligamento':
            corrida_texto = "Desligamento"
        else:
            corrida_texto = tipo_corrida or "Não informado"
        
        return f"{linha_texto} - {corrida_texto}"
    
    def _get_horario_viagem(self, viagem) -> tuple:
        """
        Obtém o horário da viagem baseado nos campos disponíveis
        
        Args:
            viagem: Objeto Viagem
            
        Returns:
            Tupla (data_formatada, horario_formatado)
        """
        # Prioridade: horario_entrada > horario_saida > horario_desligamento
        horario = None
        
        if hasattr(viagem, 'horario_entrada') and viagem.horario_entrada:
            horario = viagem.horario_entrada
        elif hasattr(viagem, 'horario_saida') and viagem.horario_saida:
            horario = viagem.horario_saida
        elif hasattr(viagem, 'horario_desligamento') and viagem.horario_desligamento:
            horario = viagem.horario_desligamento
        
        if horario:
            data_formatada = horario.strftime('%d/%m/%Y')
            horario_formatado = horario.strftime('%H:%M')
            return (data_formatada, horario_formatado)
        else:
            return ("Não informada", "Não informado")
    
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
        • Data: [DD/MM/YYYY]
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
        
        # Dados da viagem - CORRIGIDO: usando campos corretos
        tipo_viagem = self._get_tipo_viagem_formatado(viagem)
        data_formatada, horario_formatado = self._get_horario_viagem(viagem)
        
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
• Data: {data_formatada}
• Horário: {horario_formatado}

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
        
        # Formata data - CORRIGIDO
        data_formatada, horario_formatado = self._get_horario_viagem(viagem)
        data_hora_completa = f"{data_formatada} às {horario_formatado}"
        
        # Calcula valor do repasse (se disponível)
        valor_repasse = viagem.valor_repasse if hasattr(viagem, 'valor_repasse') and viagem.valor_repasse else 0
        
        # Tipo da viagem - CORRIGIDO
        tipo_viagem = self._get_tipo_viagem_formatado(viagem)
        
        mensagem = f"""🚗 *Nova Viagem Atribuída!*

Olá {motorista.nome},

Uma nova viagem foi atribuída a você:

📋 *Detalhes da Viagem*
• ID: #{viagem.id}
• Data/Hora: {data_hora_completa}
• Tipo: {tipo_viagem}
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
        
        # Formata datas - CORRIGIDO
        if hasattr(viagem, 'data_inicio') and viagem.data_inicio:
            data_inicio = viagem.data_inicio.strftime('%d/%m/%Y %H:%M')
        else:
            data_inicio = "N/A"
        
        if hasattr(viagem, 'data_finalizacao') and viagem.data_finalizacao:
            data_fim = viagem.data_finalizacao.strftime('%d/%m/%Y %H:%M')
        else:
            data_fim = "N/A"
        
        # Valor do repasse
        valor_repasse = viagem.valor_repasse if hasattr(viagem, 'valor_repasse') and viagem.valor_repasse else 0
        
        # Tipo da viagem - CORRIGIDO
        tipo_viagem = self._get_tipo_viagem_formatado(viagem)
        
        mensagem = f"""✅ *Viagem Finalizada com Sucesso!*

Olá {motorista.nome},

Sua viagem foi finalizada:

📋 *Resumo da Viagem*
• ID: #{viagem.id}
• Tipo: {tipo_viagem}
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
    
    def send_notification_viagem_cancelada(self, viagem, motivo: str = None) -> int:
        """
        Envia notificação para colaboradores quando uma viagem é cancelada
        
        Args:
            viagem: Objeto Viagem do banco de dados
            motivo: Motivo do cancelamento (opcional)
        
        Returns:
            Número de mensagens enviadas com sucesso
        """
        if not self.enabled or not self.send_notifications:
            logger.info("Notificações WhatsApp desabilitadas")
            return 0
        
        enviadas = 0
        
        # Busca todos os colaboradores da viagem
        solicitacoes = viagem.solicitacoes
        
        if not solicitacoes:
            logger.warning(f"Viagem {viagem.id} não tem solicitações/colaboradores")
            return 0
        
        # Formata data - CORRIGIDO
        data_formatada, horario_formatado = self._get_horario_viagem(viagem)
        
        # Envia para cada colaborador
        for solicitacao in solicitacoes:
            colaborador = solicitacao.colaborador
            
            if not colaborador:
                continue
            
            if not colaborador.telefone:
                logger.warning(f"Colaborador {colaborador.nome} não tem telefone cadastrado")
                continue
            
            # Monta a mensagem
            mensagem = f"""⚠️ *Viagem Cancelada*

Olá {colaborador.nome},

Informamos que a viagem #{viagem.id} foi cancelada.

📋 *Dados da Viagem*
• Data: {data_formatada}
• Horário: {horario_formatado}"""
            
            if motivo:
                mensagem += f"\n\n📝 *Motivo:* {motivo}"
            
            mensagem += "\n\nPor favor, entre em contato com a central para mais informações.\n\n_Mensagem automática do Go Mobi_"
            
            # Envia a mensagem
            if self.send_message(colaborador.telefone, mensagem):
                enviadas += 1
                logger.info(f"Notificação de cancelamento enviada para {colaborador.nome}")
            else:
                logger.error(f"Falha ao enviar notificação de cancelamento para {colaborador.nome}")
        
        logger.info(f"Total de notificações de cancelamento enviadas para viagem {viagem.id}: {enviadas}")
        return enviadas


# Instância global do serviço
whatsapp_service = WhatsAppService()


# Funções auxiliares para facilitar o uso
def enviar_notificacao_viagem_aceita(viagem) -> int:
    """
    Função auxiliar para enviar notificação quando viagem é aceita
    
    Args:
        viagem: Objeto Viagem
        
    Returns:
        Número de mensagens enviadas
    """
    return whatsapp_service.send_notification_viagem_aceita(viagem)


def enviar_notificacao_viagem_criada(viagem) -> bool:
    """
    Função auxiliar para enviar notificação quando viagem é criada/atribuída
    
    Args:
        viagem: Objeto Viagem
        
    Returns:
        True se enviado com sucesso
    """
    return whatsapp_service.send_notification_viagem_criada(viagem)


def enviar_notificacao_viagem_finalizada(viagem) -> bool:
    """
    Função auxiliar para enviar notificação quando viagem é finalizada
    
    Args:
        viagem: Objeto Viagem
        
    Returns:
        True se enviado com sucesso
    """
    return whatsapp_service.send_notification_viagem_finalizada(viagem)


def enviar_notificacao_viagem_cancelada(viagem, motivo: str = None) -> int:
    """
    Função auxiliar para enviar notificação quando viagem é cancelada
    
    Args:
        viagem: Objeto Viagem
        motivo: Motivo do cancelamento (opcional)
        
    Returns:
        Número de mensagens enviadas
    """
    return whatsapp_service.send_notification_viagem_cancelada(viagem, motivo)


def verificar_conexao_whatsapp() -> bool:
    """
    Função auxiliar para verificar se o WhatsApp está conectado
    
    Returns:
        True se conectado, False caso contrário
    """
    return whatsapp_service.check_connection()

