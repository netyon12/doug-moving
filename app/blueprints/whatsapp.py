# app/blueprints/whatsapp.py
"""
Módulo de integração com WhatsApp via Evolution API
Responsável por enviar notificações automáticas para colaboradores
"""

import requests
import os
from flask import current_app
from datetime import datetime


class WhatsAppService:
    """Serviço de envio de mensagens WhatsApp via Evolution API"""
    
    def __init__(self):
        """Inicializa o serviço com as configurações da Evolution API"""
        self.api_url = os.getenv('EVOLUTION_API_URL', 'https://evolution-api-gomobi.onrender.com')
        self.api_key = os.getenv('EVOLUTION_API_KEY', 'GoMobi2024SecretKey!@#')
        self.instance = os.getenv('EVOLUTION_INSTANCE', 'gomobi_whatsapp')
        
    def _format_phone(self, phone):
        """
        Formata o número de telefone para o padrão internacional
        
        Args:
            phone (str): Número de telefone (pode ter vários formatos)
            
        Returns:
            str: Número formatado (ex: 5512996108116)
        """
        if not phone:
            return None
            
        # Remove todos os caracteres não numéricos
        phone = ''.join(filter(str.isdigit, phone))
        
        # Se não começar com 55, adiciona (código do Brasil)
        if not phone.startswith('55'):
            phone = '55' + phone
            
        # Verifica se tem pelo menos 12 dígitos (55 + DDD + número)
        if len(phone) < 12:
            current_app.logger.warning(f"Número de telefone inválido: {phone}")
            return None
            
        return phone
    
    def _check_connection(self):
        """
        Verifica se a instância do WhatsApp está conectada
        
        Returns:
            bool: True se conectado, False caso contrário
        """
        try:
            url = f"{self.api_url}/instance/connectionState/{self.instance}"
            headers = {'apikey': self.api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                is_connected = data.get('state') == 'open'
                
                if not is_connected:
                    current_app.logger.warning(f"WhatsApp não conectado. Estado: {data.get('state')}")
                    
                return is_connected
            else:
                current_app.logger.error(f"Erro ao verificar conexão: {response.status_code}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Erro ao verificar conexão WhatsApp: {str(e)}")
            return False
    
    def send_text_message(self, phone, message):
        """
        Envia mensagem de texto para um número
        
        Args:
            phone (str): Número de telefone do destinatário
            message (str): Texto da mensagem
            
        Returns:
            dict: Resposta da API ou None em caso de erro
        """
        try:
            # Formata o número
            formatted_phone = self._format_phone(phone)
            if not formatted_phone:
                current_app.logger.error(f"Número de telefone inválido: {phone}")
                return None
            
            # Verifica conexão
            if not self._check_connection():
                current_app.logger.error("WhatsApp não está conectado")
                return None
            
            # Envia a mensagem
            url = f"{self.api_url}/message/sendText/{self.instance}"
            headers = {
                'Content-Type': 'application/json',
                'apikey': self.api_key
            }
            payload = {
                'number': formatted_phone,
                'text': message
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 201 or response.status_code == 200:
                current_app.logger.info(f"Mensagem enviada com sucesso para {formatted_phone}")
                return response.json()
            else:
                current_app.logger.error(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Erro ao enviar mensagem WhatsApp: {str(e)}")
            return None
    
    def send_viagem_confirmada(self, viagem, colaborador):
        """
        Envia mensagem de confirmação de viagem para o colaborador
        
        Args:
            viagem: Objeto Viagem
            colaborador: Objeto Colaborador
            
        Returns:
            dict: Resposta da API ou None em caso de erro
        """
        try:
            # Verifica se o colaborador tem telefone
            if not colaborador.telefone:
                current_app.logger.warning(f"Colaborador {colaborador.nome} não tem telefone cadastrado")
                return None
            
            # Busca informações do motorista
            motorista_nome = viagem.motorista.nome if viagem.motorista else "Não atribuído"
            veiculo_modelo = viagem.motorista.veiculo_modelo if viagem.motorista else "N/A"
            veiculo_cor = viagem.motorista.veiculo_cor if viagem.motorista else "N/A"
            veiculo_placa = viagem.veiculo_placa or "N/A"
            
            # Busca informações da empresa/planta
            # Assumindo que a viagem tem relacionamento com solicitações
            # e solicitações têm relacionamento com colaborador que tem empresa
            empresa_nome = "N/A"
            planta_nome = "N/A"
            
            if colaborador.empresa:
                empresa_nome = colaborador.empresa.nome
            
            if colaborador.planta:
                planta_nome = colaborador.planta.nome
            
            # Formata data e horário
            if viagem.data_viagem:
                data_formatada = viagem.data_viagem.strftime('%d/%m/%Y')
            else:
                data_formatada = "A definir"
            
            if viagem.horario_entrada:
                horario_formatado = viagem.horario_entrada.strftime('%H:%M')
            else:
                horario_formatado = "A definir"
            
            # Monta a mensagem com emojis
            message = f"""🚗 *Seja Bem-Vindo à Go Mobi!*

✅ Sua Viagem *#{viagem.id}* foi confirmada pelo Motorista *{motorista_nome}*.

📋 *Dados da Viagem:*

🏢 *Empresa:* {empresa_nome}
🏭 *Planta:* {planta_nome}
📅 *Data:* {data_formatada}
🕐 *Horário:* {horario_formatado}

👨‍✈️ *Motorista:* {motorista_nome}
🚙 *Veículo:* {veiculo_modelo}
🎨 *Cor:* {veiculo_cor}
🚗 *Placa:* {veiculo_placa}

_Tenha uma ótima viagem!_ 🌟"""
            
            # Envia a mensagem
            return self.send_text_message(colaborador.telefone, message)
            
        except Exception as e:
            current_app.logger.error(f"Erro ao enviar mensagem de viagem confirmada: {str(e)}")
            return None
    
    def send_viagem_cancelada(self, viagem, colaborador, motivo=None):
        """
        Envia mensagem de cancelamento de viagem para o colaborador
        
        Args:
            viagem: Objeto Viagem
            colaborador: Objeto Colaborador
            motivo (str, optional): Motivo do cancelamento
            
        Returns:
            dict: Resposta da API ou None em caso de erro
        """
        try:
            if not colaborador.telefone:
                current_app.logger.warning(f"Colaborador {colaborador.nome} não tem telefone cadastrado")
                return None
            
            # Monta a mensagem
            message = f"""⚠️ *Atenção!*

❌ Sua Viagem *#{viagem.id}* foi cancelada.

👤 *Colaborador:* {colaborador.nome}"""
            
            if motivo:
                message += f"\n\n📝 *Motivo:* {motivo}"
            
            message += "\n\n_Entre em contato com a Go Mobi para mais informações._"
            
            # Envia a mensagem
            return self.send_text_message(colaborador.telefone, message)
            
        except Exception as e:
            current_app.logger.error(f"Erro ao enviar mensagem de viagem cancelada: {str(e)}")
            return None


# Instância global do serviço
whatsapp_service = WhatsAppService()


def enviar_notificacao_viagem_aceita(viagem):
    """
    Função auxiliar para enviar notificação quando viagem é aceita
    Envia mensagem para todos os colaboradores da viagem
    
    Args:
        viagem: Objeto Viagem
        
    Returns:
        list: Lista de resultados do envio
    """
    from app.models import Solicitacao, Colaborador
    
    resultados = []
    
    try:
        # Busca todas as solicitações da viagem
        solicitacoes = Solicitacao.query.filter_by(viagem_id=viagem.id).all()
        
        # Envia mensagem para cada colaborador
        for solicitacao in solicitacoes:
            colaborador = solicitacao.colaborador
            
            if colaborador and colaborador.telefone:
                resultado = whatsapp_service.send_viagem_confirmada(viagem, colaborador)
                resultados.append({
                    'colaborador': colaborador.nome,
                    'telefone': colaborador.telefone,
                    'sucesso': resultado is not None
                })
                
        current_app.logger.info(f"Enviadas {len(resultados)} notificações para viagem #{viagem.id}")
        return resultados
        
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar notificações da viagem #{viagem.id}: {str(e)}")
        return resultados


def enviar_notificacao_viagem_cancelada(viagem, motivo=None):
    """
    Função auxiliar para enviar notificação quando viagem é cancelada
    Envia mensagem para todos os colaboradores da viagem
    
    Args:
        viagem: Objeto Viagem
        motivo (str, optional): Motivo do cancelamento
        
    Returns:
        list: Lista de resultados do envio
    """
    from app.models import Solicitacao, Colaborador
    
    resultados = []
    
    try:
        # Busca todas as solicitações da viagem
        solicitacoes = Solicitacao.query.filter_by(viagem_id=viagem.id).all()
        
        # Envia mensagem para cada colaborador
        for solicitacao in solicitacoes:
            colaborador = solicitacao.colaborador
            
            if colaborador and colaborador.telefone:
                resultado = whatsapp_service.send_viagem_cancelada(viagem, colaborador, motivo)
                resultados.append({
                    'colaborador': colaborador.nome,
                    'telefone': colaborador.telefone,
                    'sucesso': resultado is not None
                })
                
        current_app.logger.info(f"Enviadas {len(resultados)} notificações de cancelamento para viagem #{viagem.id}")
        return resultados
        
    except Exception as e:
        current_app.logger.error(f"Erro ao enviar notificações de cancelamento da viagem #{viagem.id}: {str(e)}")
        return resultados

