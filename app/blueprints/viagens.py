"""
Módulo de Viagens
=================

Gestão de viagens.
"""

from app.services.notification_service import notification_service
from .admin import admin_bp
from app import query_filters
from app.utils.user_sync import get_current_user_id_in_current_db
from ..decorators import permission_required
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao, ViagemHoraParada
)
from .. import db
from ..config.tenant_utils import query_tenant, get_tenant_session, get_or_404_tenant
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from io import StringIO
import io
import csv
import json
import logging
import traceback

# Configurar logger para este módulo
logger = logging.getLogger(__name__)


# Importação do serviço de notificações


@admin_bp.route('/viagens')
@login_required
@permission_required(['admin', 'gerente', 'supervisor', 'operador'])
def viagens():
    """Lista e filtra viagens criadas no sistema"""
    try:
        # Busca base de viagens (com eager loading de hora_parada)
        query = query_tenant(Viagem).options(db.joinedload(Viagem.hora_parada))

        # Inicializa variáveis de filtro
        filtro_viagem_id = request.args.get('viagem_id', '')
        filtro_status = request.args.get('status', '')

        # ===== FILTRO PADRÃO DO MÊS ATUAL =====
        # Se não houver filtros de data, aplica o mês atual como padrão
        if not request.args.get('data_inicio') and not request.args.get('data_fim'):
            hoje = date.today()
            primeiro_dia_mes = date(hoje.year, hoje.month, 1)

            # Calcula o último dia do mês
            if hoje.month == 12:
                ultimo_dia_mes = date(hoje.year, 12, 31)
            else:
                proximo_mes = date(hoje.year, hoje.month + 1, 1)
                from datetime import timedelta
                ultimo_dia_mes = proximo_mes - timedelta(days=1)

            # Define os valores padrão para os filtros
            filtro_data_inicio = primeiro_dia_mes.strftime('%Y-%m-%d')
            filtro_data_fim = ultimo_dia_mes.strftime('%Y-%m-%d')

            # Aplica os filtros na query
            data_inicio = datetime.combine(
                primeiro_dia_mes, datetime.min.time())
            data_fim = datetime.combine(ultimo_dia_mes, datetime.max.time())

            query = query.filter(
                or_(
                    Viagem.horario_entrada >= data_inicio,
                    Viagem.horario_saida >= data_inicio,
                    Viagem.horario_desligamento >= data_inicio
                )
            )
            query = query.filter(
                or_(
                    Viagem.horario_entrada <= data_fim,
                    Viagem.horario_saida <= data_fim,
                    Viagem.horario_desligamento <= data_fim
                )
            )
        else:
            # Se houver filtros, usa os valores dos request.args
            filtro_data_inicio = request.args.get('data_inicio', '')
            filtro_data_fim = request.args.get('data_fim', '')
        # ===== FIM DO FILTRO PADRÃO =====

        # Aplica filtro de ID Viagem
        if filtro_viagem_id:
            query = query.filter(Viagem.id == int(filtro_viagem_id))

        # Aplica filtro de Status
        if filtro_status:
            query = query.filter(Viagem.status == filtro_status)

        # Aplica filtro de Data Início (se houver filtro personalizado)
        if filtro_data_inicio:
            data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d')
            query = query.filter(
                or_(
                    Viagem.horario_entrada >= data_inicio,
                    Viagem.horario_saida >= data_inicio,
                    Viagem.horario_desligamento >= data_inicio
                )
            )

        # Aplica filtro de Data Fim (se houver filtro personalizado)
        if filtro_data_fim:
            data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d')
            data_fim = data_fim.replace(hour=23, minute=59, second=59)
            query = query.filter(
                or_(
                    Viagem.horario_entrada <= data_fim,
                    Viagem.horario_saida <= data_fim,
                    Viagem.horario_desligamento <= data_fim
                )
            )

        filtro_motorista_id = request.args.get('motorista_id', '')
        if filtro_motorista_id:
            query = query.filter(Viagem.motorista_id ==
                                 int(filtro_motorista_id))

        filtro_bloco_id = request.args.get('bloco_id', '')
        if filtro_bloco_id:
            query = query.filter(Viagem.bloco_id == int(filtro_bloco_id))

        filtro_planta_id = request.args.get('planta_id', '')
        if filtro_planta_id:
            query = query.filter(Viagem.planta_id == int(filtro_planta_id))

        # Ordena por data/horário mais recente
        # Otimização: Eager loading para evitar N+1 queries
        viagens = query.options(
            joinedload(Viagem.motorista),
            joinedload(Viagem.bloco),
            joinedload(Viagem.planta),
            joinedload(Viagem.empresa),
            joinedload(Viagem.hora_parada)
        ).order_by(Viagem.id.desc()).limit(500).all()

        # Busca dados para os filtros
        motoristas = query_tenant(Motorista).order_by(Motorista.nome).all()
        blocos = query_tenant(Bloco).order_by(Bloco.codigo_bloco).all()
        plantas = query_tenant(Planta).order_by(Planta.nome).all()

        # Opções de status
        status_opcoes = ['Pendente', 'Agendada',
                         'Em Andamento', 'Finalizada', 'Cancelada']

        return render_template(
            'admin/admin_viagens.html',
            viagens=viagens,
            motoristas=motoristas,
            blocos=blocos,
            plantas=plantas,
            status_opcoes=status_opcoes,
            filtro_viagem_id=filtro_viagem_id,
            filtro_status=filtro_status,
            filtro_data_inicio=filtro_data_inicio,
            filtro_data_fim=filtro_data_fim,
            filtro_motorista_id=filtro_motorista_id,
            filtro_bloco_id=filtro_bloco_id,
            filtro_planta_id=filtro_planta_id
        )

    except Exception as e:
        flash(f'Erro ao carregar viagens: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/viagens/<int:viagem_id>/detalhes')
@login_required
@permission_required(['admin', 'gerente', 'supervisor', 'operador'])
def viagem_detalhes(viagem_id):
    """Retorna os detalhes completos de uma viagem específica em JSON"""
    try:
        viagem = get_or_404_tenant(Viagem, viagem_id)

        # Monta dados do motorista com tratamento seguro
        motorista_info = None
        if viagem.motorista_id and viagem.motorista:
            motorista_info = {
                'id': viagem.motorista_id,
                'nome': viagem.motorista.nome or 'N/A',
                'telefone': viagem.motorista.telefone or 'N/A',
                'veiculo_nome': viagem.motorista.veiculo_nome or 'N/A',
                'veiculo_placa': viagem.motorista.veiculo_placa or 'N/A'
            }

        # [OK] NOVA LÓGICA: Busca colaboradores do campo viagem.colaboradores_ids
        colaboradores_lista = []

        if viagem.colaboradores_ids:
            try:
                # Parse do JSON: "[461, 648, 649]" → [461, 648, 649]
                colaboradores_ids = json.loads(viagem.colaboradores_ids)

                # Busca todos os colaboradores de uma vez (mais eficiente)
                colaboradores = query_tenant(Colaborador).filter(
                    Colaborador.id.in_(colaboradores_ids)
                ).all()

                # Monta lista de colaboradores com detalhes
                for colaborador in colaboradores:
                    colaboradores_lista.append({
                        'id': colaborador.id,
                        'colaborador_nome': colaborador.nome,
                        'colaborador_matricula': colaborador.matricula if hasattr(colaborador, 'matricula') else 'N/A',
                        'colaborador_telefone': colaborador.telefone if hasattr(colaborador, 'telefone') else 'N/A',
                        'endereco': colaborador.endereco or 'N/A',
                        'bairro': colaborador.bairro or 'N/A',
                        'status': 'N/A'
                    })

            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    f"[ERRO] Erro ao parsear colaboradores_ids da viagem {viagem_id}: {e}")

        # Monta dados completos da viagem
        dados_viagem = {
            'id': viagem.id,
            'status': viagem.status or 'N/A',
            'tipo_corrida': viagem.tipo_corrida or 'N/A',
            'quantidade_passageiros': viagem.quantidade_passageiros or 0,

            # Horários
            'horario_entrada': viagem.horario_entrada.strftime('%d/%m/%Y %H:%M') if viagem.horario_entrada else None,
            'horario_saida': viagem.horario_saida.strftime('%d/%m/%Y %H:%M') if viagem.horario_saida else None,
            'horario_desligamento': viagem.horario_desligamento.strftime('%d/%m/%Y %H:%M') if viagem.horario_desligamento else None,

            # Valores
            'valor': float(viagem.valor) if viagem.valor else 0.00,
            'valor_repasse': float(viagem.valor_repasse) if viagem.valor_repasse else 0.00,

            # Localização
            'bloco_codigo': viagem.bloco.codigo_bloco if viagem.bloco else 'N/A',
            'planta_nome': viagem.planta.nome if viagem.planta else 'N/A',
            'empresa_nome': viagem.empresa.nome if viagem.empresa else 'N/A',

            # Motorista
            'motorista': motorista_info,

            # Colaboradores/Solicitações
            'colaboradores': colaboradores_lista,
            'total_colaboradores': len(colaboradores_lista),

            # Timestamps
            'criado_em': viagem.data_criacao.strftime('%d/%m/%Y %H:%M') if viagem.data_criacao else 'N/A',
            'atualizado_em': viagem.data_atualizacao.strftime('%d/%m/%Y %H:%M') if viagem.data_atualizacao else 'N/A'
        }

        return jsonify({'success': True, 'viagem': dados_viagem})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(
            f"[ERRO] Erro ao buscar detalhes da viagem {viagem_id}: {error_details}")
        return jsonify({'success': False, 'message': f'Erro ao carregar detalhes: {str(e)}'}), 500


@admin_bp.route('/motoristas_disponiveis')
@login_required
@permission_required(['admin', 'supervisor', 'operador'])
def motoristas_disponiveis():
    """Retorna lista de motoristas disponíveis para associação"""
    try:
        motoristas = query_tenant(Motorista).filter_by(
            status='Ativo').order_by(Motorista.nome).all()

        dados_motoristas = [
            {
                'id': m.id,
                'nome': m.nome,
                'telefone': m.telefone,
                'veiculo': m.veiculo_nome,
                'placa': m.veiculo_placa,
                'capacidade': 4  # Capacidade padrão, pode ser ajustado
            }
            for m in motoristas
        ]

        return jsonify({'success': True, 'motoristas': dados_motoristas})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/associar_motorista', methods=['POST'])
@login_required
@permission_required(['admin', 'operador'])
def associar_motorista(viagem_id):
    """Associa um motorista a uma viagem"""
    logger.info(
        f"[>>>] Iniciando associação de motorista para viagem {viagem_id}")
    try:
        data = request.get_json()
        motorista_id = data.get('motorista_id')

        if not motorista_id:
            return jsonify({'success': False, 'message': 'Motorista não informado'}), 400

        # Busca viagem e motorista
        viagem = get_or_404_tenant(Viagem, viagem_id)
        motorista = get_or_404_tenant(Motorista, motorista_id)

        logger.info(
            f"[...] Associando motorista {motorista.nome} (ID: {motorista_id}) à viagem {viagem_id}")

        # Verifica se a viagem está pendente
        if viagem.status != 'Pendente':
            return jsonify({'success': False, 'message': 'Apenas viagens pendentes podem ter motorista associado'}), 400

        # Verifica capacidade do motorista (capacidade padrão de 4 passageiros)
        capacidade_veiculo = 4
        if viagem.quantidade_passageiros > capacidade_veiculo:
            return jsonify({
                'success': False,
                'message': f'Veículo tem capacidade para {capacidade_veiculo} passageiros, mas a viagem tem {viagem.quantidade_passageiros}'
            }), 400

        # Associa motorista usando método do modelo
        sucesso = viagem.aceitar_viagem(motorista)

        if not sucesso:
            return jsonify({
                'success': False,
                'message': 'Não foi possível associar motorista à viagem'
            }), 400

        get_tenant_session().commit()

        # ========== INTEGRAÇÃO WHATSAPP - INÍCIO ==========
        # Envia notificação WhatsApp para colaboradores (exceto Desligamento)
        if viagem.tipo_corrida != 'desligamento':
            try:
                sucesso = notification_service.notificar_viagem_confirmada(
                    viagem_id=viagem.id,
                    motorista_id=motorista_id
                )
                from flask import current_app
                if sucesso:
                    current_app.logger.info(
                        f"WhatsApp enviado para colaboradores da viagem {viagem.id} (associação admin)")
            except Exception as e:
                # Não interrompe o fluxo se o WhatsApp falhar
                from flask import current_app
                current_app.logger.error(f"Erro ao enviar WhatsApp: {str(e)}")

        # ========== INTEGRAÇÃO WHATSAPP - FIM ==========

        flash(
            f'Motorista {motorista.nome} associado à viagem #{viagem.id} com sucesso!', 'success')
        return jsonify({'success': True, 'message': 'Motorista associado com sucesso'})

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/cancelar', methods=['POST'])
@login_required
@permission_required(['admin', 'operador', 'gerente', 'supervisor'])
def cancelar_viagem(viagem_id):
    """Cancela uma viagem e retorna as solicitações para status Pendente"""
    logger.info(f"[CANCEL] Iniciando cancelamento da viagem {viagem_id}")
    try:
        data = request.get_json()
        motivo = data.get('motivo', '')

        if not motivo:
            return jsonify({'success': False, 'message': 'Motivo do cancelamento é obrigatório'}), 400

        # Busca viagem
        viagem = get_or_404_tenant(Viagem, viagem_id)

        logger.info(f"[...] Cancelando viagem {viagem_id} - Motivo: {motivo}")

        # Verifica se a viagem pode ser cancelada (regras por status)
        if viagem.status in ['Finalizada', 'Cancelada']:
            return jsonify({'success': False, 'message': 'Esta viagem não pode ser cancelada'}), 400
        
        # Em Andamento: NINGUÉM pode cancelar (deve finalizar)
        if viagem.status == 'Em Andamento':
            return jsonify({
                'success': False, 
                'message': 'Viagens em andamento não podem ser canceladas. Aguarde a finalização.'
            }), 400
        
        # Agendada: Apenas Admin e Operador podem cancelar
        if viagem.status == 'Agendada':
            if current_user.role not in ['admin', 'operador']:
                return jsonify({
                    'success': False, 
                    'message': 'Viagens agendadas só podem ser canceladas por Admin ou Operador (motorista já foi notificado).'
                }), 403
        
        # Pendente: Verifica permissão por perfil
        if viagem.status == 'Pendente':
            if current_user.role in ['gerente', 'supervisor']:
                # Gerente e Supervisor: Apenas viagens criadas por eles
                from app.utils.user_sync import get_current_user_id_in_current_db
                user_id_atual = get_current_user_id_in_current_db()
                
                if viagem.created_by_user_id != user_id_atual:
                    return jsonify({
                        'success': False, 
                        'message': 'Você só pode cancelar viagens Pendentes criadas por você.'
                    }), 403
            # Admin e Operador: Podem cancelar qualquer viagem Pendente

        # Atualiza status da viagem
        viagem.status = 'Cancelada'
        viagem.motivo_cancelamento = motivo
        viagem.data_cancelamento = datetime.now()
        viagem.data_atualizacao = datetime.now()

        # Retorna solicitações para status Pendente
        solicitacoes = query_tenant(Solicitacao).filter_by(viagem_id=viagem_id).all()
        for solicitacao in solicitacoes:
            solicitacao.status = 'Pendente'
            solicitacao.viagem_id = None

        get_tenant_session().commit()

        # ========== INTEGRAÇÃO WHATSAPP - INÍCIO ==========
        # Envia notificação WhatsApp para colaboradores sobre cancelamento
        if viagem.tipo_corrida != 'desligamento':
            try:
                resultado = notification_service.notificar_viagem_cancelada_colaboradores(
                    viagem_id=viagem.id,
                    motivo_cancelamento=motivo
                )

                from flask import current_app
                if resultado['success']:
                    current_app.logger.info(
                        f"[OK] WhatsApp de cancelamento enviado para {resultado['enviadas']} colaborador(es) da viagem {viagem.id}")
                else:
                    current_app.logger.warning(
                        f"[AVISO] Falha ao enviar WhatsApp de cancelamento para viagem {viagem.id}")
            except Exception as e:
                # Não interrompe o fluxo se o WhatsApp falhar
                from flask import current_app
                current_app.logger.error(
                    f"[ERRO] Erro ao enviar WhatsApp de cancelamento: {str(e)}")
        # ========== INTEGRAÇÃO WHATSAPP - FIM ==========

        flash(
            f'Viagem #{viagem.id} cancelada. {len(solicitacoes)} solicitações retornaram para status Pendente.', 'warning')
        return jsonify({
            'success': True,
            'message': f'Viagem cancelada com sucesso. {len(solicitacoes)} solicitações retornaram para Pendente.'
        })

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ===========================================================================================
# ROTAS DE HORA PARADA
# ===========================================================================================

@admin_bp.route('/viagens/<int:viagem_id>/hora-parada', methods=['GET'])
@login_required
@permission_required(['admin', 'operador'])
def viagem_hora_parada_form(viagem_id):
    """
    Exibe o formulário (modal) para adicionar/editar hora parada em uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada
        import math

        # Busca a viagem
        viagem = get_or_404_tenant(Viagem, viagem_id)

        # Verifica se a viagem está finalizada
        if viagem.status != 'Finalizada':
            return jsonify({
                'success': False,
                'message': 'Hora parada só pode ser adicionada em viagens finalizadas.'
            }), 400

        # Verifica se já existe hora parada cadastrada
        hora_parada_existente = query_tenant(ViagemHoraParada).filter_by(
            viagem_id=viagem_id).first()

        # Determina o horário agendado baseado no tipo de corrida
        horario_agendado = None
        if viagem.tipo_corrida == 'entrada':
            horario_agendado = viagem.horario_entrada
        elif viagem.tipo_corrida == 'saida':
            horario_agendado = viagem.horario_saida
        elif viagem.tipo_corrida == 'desligamento':
            horario_agendado = viagem.horario_desligamento

        # Horário real de início
        horario_real_inicio = viagem.data_inicio

        # Calcula atraso em minutos
        minutos_atraso = 0
        if horario_agendado and horario_real_inicio:
            diferenca = horario_real_inicio - horario_agendado
            minutos_atraso = int(diferenca.total_seconds() / 60)

        # Calcula períodos sugeridos
        periodos_sugeridos = ViagemHoraParada.calcular_periodos(
            minutos_atraso) if minutos_atraso > 0 else 1

        # Obtém valores configurados
        valor_periodo, repasse_periodo = ViagemHoraParada.obter_valores_configurados()

        # Prepara dados para o modal
        dados = {
            'viagem_id': viagem.id,
            'tipo_corrida': viagem.tipo_corrida,
            'motorista_nome': viagem.nome_motorista,
            'horario_agendado': horario_agendado.strftime('%d/%m/%Y %H:%M') if horario_agendado else 'N/A',
            'horario_real_inicio': horario_real_inicio.strftime('%d/%m/%Y %H:%M') if horario_real_inicio else 'N/A',
            'minutos_atraso': minutos_atraso,
            'periodos_sugeridos': periodos_sugeridos,
            'valor_periodo': float(valor_periodo),
            'repasse_periodo': float(repasse_periodo),
            'editando': hora_parada_existente is not None
        }

        # Se está editando, adiciona dados existentes
        if hora_parada_existente:
            dados['hp_id'] = hora_parada_existente.id
            dados['periodos_atual'] = hora_parada_existente.periodos_30min
            dados['observacoes_atual'] = hora_parada_existente.observacoes or ''

        return jsonify({'success': True, 'dados': dados})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/hora-parada', methods=['POST'])
@login_required
@permission_required(['admin', 'operador'])
def viagem_hora_parada_salvar(viagem_id):
    """
    Salva (cria ou atualiza) a hora parada de uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada

        # Busca a viagem
        viagem = get_or_404_tenant(Viagem, viagem_id)

        # Verifica se a viagem está finalizada
        if viagem.status != 'Finalizada':
            return jsonify({
                'success': False,
                'message': 'Hora parada só pode ser adicionada em viagens finalizadas.'
            }), 400

        # Obtém dados do formulário
        periodos_30min = int(request.form.get('periodos_30min', 1))
        observacoes = request.form.get('observacoes', '').strip()

        # Validação
        if periodos_30min < 1:
            return jsonify({
                'success': False,
                'message': 'O número de períodos deve ser maior ou igual a 1.'
            }), 400

        # Determina o horário agendado baseado no tipo de corrida
        horario_agendado = None
        if viagem.tipo_corrida == 'entrada':
            horario_agendado = viagem.horario_entrada
        elif viagem.tipo_corrida == 'saida':
            horario_agendado = viagem.horario_saida
        elif viagem.tipo_corrida == 'desligamento':
            horario_agendado = viagem.horario_desligamento

        # Horário real de início
        horario_real_inicio = viagem.data_inicio

        # Calcula atraso em minutos
        minutos_atraso = 0
        if horario_agendado and horario_real_inicio:
            diferenca = horario_real_inicio - horario_agendado
            minutos_atraso = int(diferenca.total_seconds() / 60)

        # Obtém valores configurados
        valor_periodo, repasse_periodo = ViagemHoraParada.obter_valores_configurados()

        # Calcula valores totais
        valor_adicional = valor_periodo * periodos_30min
        repasse_adicional = repasse_periodo * periodos_30min

        # Verifica se já existe hora parada
        hora_parada = query_tenant(ViagemHoraParada).filter_by(
            viagem_id=viagem_id).first()

        if hora_parada:
            # Atualiza existente
            hora_parada.periodos_30min = periodos_30min
            hora_parada.valor_adicional = valor_adicional
            hora_parada.repasse_adicional = repasse_adicional
            hora_parada.observacoes = observacoes
            mensagem = f'Hora parada da viagem #{viagem.id} atualizada com sucesso!'
        else:
            # Cria novo registro
            hora_parada = ViagemHoraParada(
                viagem_id=viagem_id,
                tipo_corrida=viagem.tipo_corrida,
                horario_agendado=horario_agendado,
                horario_real_inicio=horario_real_inicio,
                minutos_atraso=minutos_atraso,
                periodos_30min=periodos_30min,
                valor_adicional=valor_adicional,
                repasse_adicional=repasse_adicional,
                observacoes=observacoes,
                created_by_user_id=get_current_user_id_in_current_db()
            )
            get_tenant_session().add(hora_parada)
            mensagem = f'Hora parada adicionada à viagem #{viagem.id} com sucesso!'

        get_tenant_session().commit()

        flash(mensagem, 'success')
        return jsonify({
            'success': True,
            'message': mensagem,
            'valor_adicional': float(valor_adicional),
            'repasse_adicional': float(repasse_adicional)
        })

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/hora-parada', methods=['DELETE'])
@login_required
@permission_required(['admin', 'operador'])
def viagem_hora_parada_excluir(viagem_id):
    """
    Exclui a hora parada de uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada

        # Busca a hora parada
        hora_parada = query_tenant(ViagemHoraParada).filter_by(
            viagem_id=viagem_id).first()

        if not hora_parada:
            return jsonify({
                'success': False,
                'message': 'Hora parada não encontrada para esta viagem.'
            }), 404

        get_tenant_session().delete(hora_parada)
        get_tenant_session().commit()

        flash(
            f'Hora parada da viagem #{viagem_id} excluída com sucesso!', 'success')
        return jsonify({
            'success': True,
            'message': 'Hora parada excluída com sucesso!'
        })

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ===========================================================================================
# FIM DAS ROTAS DE HORA PARADA
# ===========================================================================================
