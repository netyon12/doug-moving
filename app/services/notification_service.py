"""
Serviço de Notificações via WhatsApp usando 360dialog API

Este serviço envia notificações para motoristas e colaboradores usando a API 360dialog.

Configuração necessária no .env:
- WHATSAPP_360DIALOG_API_KEY: API Key gerada no painel da 360dialog
- WHATSAPP_360DIALOG_BASE_URL: URL base da API (https://waba-v2.360dialog.io)
- WHATSAPP_PHONE_NUMBER_ID: ID do número de telefone do WhatsApp Business

Autor: Manus AI
Data: 06 de Novembro de 2025
Versão: 3.0 (FINAL - Parâmetros corretos conforme templates Meta)
"""

import os
import requests
import time
import logging
from threading import Thread
from app import db
from ..models import Motorista, Viagem, Solicitacao

logger = logging.getLogger(__name__)


class NotificationService:
    """Serviço para envio de notificações via WhatsApp usando 360dialog API"""

    def __init__(self):
        self.api_key = os.getenv('WHATSAPP_360DIALOG_API_KEY')
        self.base_url = os.getenv(
            'WHATSAPP_360DIALOG_BASE_URL', 'https://waba-v2.360dialog.io')
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')

        # URL completa da API de mensagens
        self.api_url = f"{self.base_url}/v1/messages"

        if not self.api_key:
            logger.warning("⚠️  WHATSAPP_360DIALOG_API_KEY não configurada")

        self.headers = {
            'D360-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

    def _enviar_template_whatsapp(self, telefone: str, template_name: str, parametros: list) -> bool:
        """
        Envia uma mensagem template via 360dialog API

        Args:
            telefone: Número do destinatário (formato: 5511999999999)
            template_name: Nome do template aprovado
            parametros: Lista de parâmetros do template

        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        try:
            # Formatar número (remover caracteres especiais)
            telefone_limpo = ''.join(filter(str.isdigit, telefone))

            # Adicionar código do país se não tiver
            if not telefone_limpo.startswith('55'):
                telefone_limpo = '55' + telefone_limpo

            # Montar payload da requisição (formato 360dialog)
            payload = {
                "to": telefone_limpo,
                "type": "template",
                "template": {
                    "namespace": "687185377405947",  # Namespace da sua conta Meta
                    "language": {
                        "policy": "deterministic",
                        "code": "pt_BR"
                    },
                    "name": template_name,
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": str(param)}
                                for param in parametros
                            ]
                        }
                    ]
                }
            }

            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200 or response.status_code == 201:
                logger.info(
                    f"✅ Mensagem '{template_name}' enviada para {telefone_limpo}")
                return True
            else:
                logger.error(
                    f"❌ Erro ao enviar '{template_name}' para {telefone_limpo}: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(
                f"❌ Exceção ao enviar WhatsApp para {telefone}: {str(e)}")
            return False

    def notificar_novas_viagens_em_lote(self, quantidade_viagens: int = 0) -> int:
        """
        Notifica todos os motoristas disponíveis sobre novas viagens criadas (em lote)

        Template: novas_viagens
        Parâmetros: 1
        - {{1}} Nome do motorista

        Args:
            quantidade_viagens: Quantidade de viagens criadas (para log, não usado no template)

        Returns:
            int: Número de motoristas notificados com sucesso
        """
        try:
            logger.info(
                f"📤 Iniciando envio de notificação em lote sobre {quantidade_viagens} viagem(ns) criada(s)...")

            # Buscar motoristas disponíveis
            motoristas = Motorista.query.filter_by(status='Ativo').all()

            if not motoristas:
                logger.warning("⚠️ Nenhum motorista disponível para notificar")
                return 0

            motoristas_notificados = 0

            for motorista in motoristas:
                if not motorista.telefone:
                    logger.warning(
                        f"⚠️ Motorista {motorista.nome} não tem telefone cadastrado")
                    continue

                # Enviar template 'novas_viagens' com nome do motorista
                sucesso = self._enviar_template_whatsapp(
                    telefone=motorista.telefone,
                    template_name="novas_viagens",
                    parametros=[motorista.nome]  # ✅ Apenas 1 parâmetro
                )

                if sucesso:
                    motoristas_notificados += 1

                # Intervalo de 2 segundos entre mensagens para evitar bloqueio
                time.sleep(2)

            logger.info(
                f"✅ {motoristas_notificados} motorista(s) notificado(s) sobre {quantidade_viagens} nova(s) viagem(ns)")
            return motoristas_notificados

        except Exception as e:
            logger.error(f"❌ Erro ao notificar motoristas em lote: {str(e)}")
            return 0

    def notificar_viagem_confirmada(self, viagem_id: int, motorista_id: int) -> dict:
        """
        Notifica COLABORADORES sobre confirmação de viagem

        Template: viagem_confirmada
        Parâmetros: 9
        - {{1}} Nome do Colaborador
        - {{2}} Nome do Motorista
        - {{3}} Modelo do Veículo
        - {{4}} Placa
        - {{5}} Cor do veículo
        - {{6}} Tipo de linha
        - {{7}} Tipo de corrida
        - {{8}} Data
        - {{9}} Horário

        Args:
            viagem_id: ID da viagem confirmada
            motorista_id: ID do motorista atribuído

        Returns:
            dict: {'success': bool, 'enviadas': int, 'falhas': int}
        """
        try:
            viagem = Viagem.query.get(viagem_id)
            motorista = Motorista.query.get(motorista_id)

            if not viagem:
                logger.warning(f"⚠️ Viagem {viagem_id} não encontrada")
                return {'success': False, 'enviadas': 0, 'falhas': 0}

            if not motorista:
                logger.warning(f"⚠️ Motorista {motorista_id} não encontrado")
                return {'success': False, 'enviadas': 0, 'falhas': 0}

            # Buscar colaboradores da viagem
            solicitacoes = viagem.solicitacoes

            if not solicitacoes:
                logger.warning(f"⚠️ Viagem {viagem_id} sem solicitações")
                return {'success': False, 'enviadas': 0, 'falhas': 0}

            logger.info(
                f"📤 Notificando {len(solicitacoes)} colaborador(es) sobre viagem {viagem_id}...")

            enviadas = 0
            falhas = 0

            # Preparar dados da viagem
            data_viagem = viagem.data_inicio.strftime(
                '%d/%m/%Y') if viagem.data_inicio else 'A definir'
            horario_viagem = viagem.data_inicio.strftime(
                '%H:%M') if viagem.data_inicio else 'A definir'

            # Tipo de corrida
            tipo_corrida = viagem.tipo_corrida or 'Entrada'

            # Tipo de linha (assumindo que é o mesmo que tipo_corrida, ajustar se necessário)
            tipo_linha = tipo_corrida

            # Dados do motorista
            nome_motorista = motorista.nome

            # Dados do veículo (com tratamento de erro se não existir)
            try:
                if motorista.veiculo:
                    modelo_veiculo = motorista.veiculo.modelo or 'Não informado'
                    placa_veiculo = motorista.veiculo.placa or 'Não informado'
                    cor_veiculo = motorista.veiculo.cor or 'Não informado'
                else:
                    modelo_veiculo = 'Não informado'
                    placa_veiculo = 'Não informado'
                    cor_veiculo = 'Não informado'
            except:
                modelo_veiculo = 'Não informado'
                placa_veiculo = 'Não informado'
                cor_veiculo = 'Não informado'

            # Enviar para cada colaborador
            for solicitacao in solicitacoes:
                colaborador = solicitacao.colaborador

                if not colaborador:
                    logger.warning(
                        f"⚠️ Solicitação {solicitacao.id} sem colaborador")
                    falhas += 1
                    continue

                if not colaborador.telefone:
                    logger.warning(
                        f"⚠️ Colaborador {colaborador.nome} sem telefone")
                    falhas += 1
                    continue

                # Enviar template 'viagem_confirmada' com 9 parâmetros
                sucesso = self._enviar_template_whatsapp(
                    telefone=colaborador.telefone,
                    template_name="viagem_confirmada",
                    parametros=[
                        colaborador.nome,           # {1} Nome do Colaborador
                        nome_motorista,             # {2} Nome do Motorista
                        modelo_veiculo,             # {3} Modelo do Veículo
                        placa_veiculo,              # {4} Placa
                        cor_veiculo,                # {5} Cor do veículo
                        tipo_linha,                 # {6} Tipo de linha
                        tipo_corrida,               # {7} Tipo de corrida
                        data_viagem,                # {8} Data
                        horario_viagem              # {9} Horário
                    ]
                )

                if sucesso:
                    enviadas += 1
                    logger.info(
                        f"✅ Colaborador {colaborador.nome} notificado sobre viagem {viagem_id}")
                else:
                    falhas += 1
                    logger.error(
                        f"❌ Falha ao notificar {colaborador.nome}")

                # Intervalo de 2 segundos entre mensagens
                time.sleep(2)

            logger.info(
                f"✅ Notificação concluída: {enviadas} enviadas, {falhas} falhas")

            return {
                'success': enviadas > 0,
                'enviadas': enviadas,
                'falhas': falhas
            }

        except Exception as e:
            logger.error(f"❌ Erro ao notificar confirmação: {str(e)}")
            return {'success': False, 'enviadas': 0, 'falhas': 0}

    def notificar_viagem_cancelada_colaboradores(self, viagem_id: int, motivo_cancelamento: str = '') -> dict:
        """
        Notifica COLABORADORES sobre cancelamento de viagem

        Template: viagem_cancelada
        Parâmetros: 2
        - {{1}} Nome do Colaborador
        - {{2}} ID da viagem

        NOTA: O template não usa data, horário ou motivo do cancelamento

        Args:
            viagem_id: ID da viagem cancelada
            motivo_cancelamento: Motivo do cancelamento (não usado no template)

        Returns:
            dict: {'success': bool, 'enviadas': int, 'falhas': int}
        """
        try:
            viagem = Viagem.query.get(viagem_id)

            if not viagem:
                logger.warning(f"⚠️ Viagem {viagem_id} não encontrada")
                return {'success': False, 'enviadas': 0, 'falhas': 0}

            # Buscar colaboradores da viagem
            solicitacoes = viagem.solicitacoes

            if not solicitacoes:
                logger.warning(f"⚠️ Viagem {viagem_id} sem solicitações")
                return {'success': False, 'enviadas': 0, 'falhas': 0}

            logger.info(
                f"📤 Notificando {len(solicitacoes)} colaborador(es) sobre cancelamento da viagem {viagem_id}...")

            enviadas = 0
            falhas = 0

            # Enviar para cada colaborador
            for solicitacao in solicitacoes:
                colaborador = solicitacao.colaborador

                if not colaborador:
                    logger.warning(
                        f"⚠️ Solicitação {solicitacao.id} sem colaborador")
                    falhas += 1
                    continue

                if not colaborador.telefone:
                    logger.warning(
                        f"⚠️ Colaborador {colaborador.nome} sem telefone")
                    falhas += 1
                    continue

                # Enviar template 'viagem_cancelada' com 2 parâmetros
                sucesso = self._enviar_template_whatsapp(
                    telefone=colaborador.telefone,
                    template_name="viagem_cancelada",
                    parametros=[
                        colaborador.nome,           # {1} Nome do Colaborador
                        str(viagem_id)              # {2} ID da viagem
                    ]
                )

                if sucesso:
                    enviadas += 1
                    logger.info(
                        f"✅ Colaborador {colaborador.nome} notificado sobre cancelamento da viagem {viagem_id}")
                else:
                    falhas += 1
                    logger.error(
                        f"❌ Falha ao notificar {colaborador.nome}")

                # Intervalo de 2 segundos entre mensagens
                time.sleep(2)

            logger.info(
                f"✅ Notificação de cancelamento concluída: {enviadas} enviadas, {falhas} falhas")

            return {
                'success': enviadas > 0,
                'enviadas': enviadas,
                'falhas': falhas
            }

        except Exception as e:
            logger.error(f"❌ Erro ao notificar cancelamento: {str(e)}")
            return {'success': False, 'enviadas': 0, 'falhas': 0}


# Instância global do serviço
notification_service = NotificationService()


# Função auxiliar para enviar notificações em thread separada
def enviar_notificacao_async(func, *args, **kwargs):
    """
    Executa uma função de notificação em uma thread separada
    para não bloquear a aplicação principal
    """
    thread = Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
