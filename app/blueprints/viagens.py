"""
Módulo de Viagens
=================

Gestão de viagens.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from sqlalchemy import func, or_
from io import StringIO
import io
import csv

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao, ViagemHoraParada
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp

# Importação do serviço de WhatsApp
from app.services.whatsapp_service import whatsapp_service


@admin_bp.route('/viagens')
@login_required
@permission_required(['admin', 'gerente', 'supervisor'])
def viagens():
    """Lista e filtra viagens criadas no sistema"""
    try:
        # Busca base de viagens (com eager loading de hora_parada)
        query = Viagem.query.options(db.joinedload(Viagem.hora_parada))

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
        viagens = query.order_by(Viagem.id.desc()).all()

        # Busca dados para os filtros
        motoristas = Motorista.query.order_by(Motorista.nome).all()
        blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
        plantas = Planta.query.order_by(Planta.nome).all()

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
@permission_required(['admin', 'gerente', 'supervisor'])
def viagem_detalhes(viagem_id):
    """Retorna os detalhes completos de uma viagem específica em JSON"""
    try:
        viagem = Viagem.query.get_or_404(viagem_id)

        # Busca solicitações associadas
        solicitacoes = Solicitacao.query.filter_by(viagem_id=viagem_id).all()

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

        # Monta lista de colaboradores com detalhes
        colaboradores_lista = []
        for s in solicitacoes:
            if s.colaborador:
                colaboradores_lista.append({
                    'id': s.id,
                    'colaborador_nome': s.colaborador.nome,
                    'colaborador_matricula': s.colaborador.matricula if hasattr(s.colaborador, 'matricula') else 'N/A',
                    'colaborador_telefone': s.colaborador.telefone if hasattr(s.colaborador, 'telefone') else 'N/A',
                    'endereco': s.colaborador.endereco or 'N/A',
                    'bairro': s.colaborador.bairro or 'N/A',
                    'status': s.status or 'N/A'
                })

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
        print(
            f"Erro ao buscar detalhes da viagem {viagem_id}: {error_details}")
        return jsonify({'success': False, 'message': f'Erro ao carregar detalhes: {str(e)}'}), 500


@admin_bp.route('/motoristas_disponiveis')
@login_required
@permission_required(['admin', 'supervisor'])
def motoristas_disponiveis():
    """Retorna lista de motoristas disponíveis para associação"""
    try:
        motoristas = Motorista.query.filter_by(
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
@permission_required(['admin'])
def associar_motorista(viagem_id):
    """Associa um motorista a uma viagem"""
    try:
        data = request.get_json()
        motorista_id = data.get('motorista_id')

        if not motorista_id:
            return jsonify({'success': False, 'message': 'Motorista não informado'}), 400

        # Busca viagem e motorista
        viagem = Viagem.query.get_or_404(viagem_id)
        motorista = Motorista.query.get_or_404(motorista_id)

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

        # Associa motorista
        viagem.motorista_id = motorista.id
        viagem.nome_motorista = motorista.nome
        viagem.placa_veiculo = motorista.veiculo_placa
        viagem.status = 'Agendada'
        viagem.data_atualizacao = datetime.now()

        db.session.commit()

        # ========== INTEGRAÇÃO WHATSAPP - INÍCIO ==========
        # Envia notificação WhatsApp para colaboradores (exceto Desligamento)
        if viagem.tipo_corrida != 'desligamento':
            try:
                resultados_whatsapp = whatsapp_service.send_notification_viagem_aceita(
                    viagem)
                from flask import current_app
                current_app.logger.info(
                    f"WhatsApp enviado para {len(resultados_whatsapp)} colaboradores (associação admin)")
            except Exception as e:
                # Não interrompe o fluxo se o WhatsApp falhar
                from flask import current_app
                current_app.logger.error(f"Erro ao enviar WhatsApp: {str(e)}")

        # ========== INTEGRAÇÃO WHATSAPP - FIM ==========

        flash(
            f'Motorista {motorista.nome} associado à viagem #{viagem.id} com sucesso!', 'success')
        return jsonify({'success': True, 'message': 'Motorista associado com sucesso'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/cancelar', methods=['POST'])
@login_required
@permission_required(['admin', 'gerente', 'supervisor'])
def cancelar_viagem(viagem_id):
    """Cancela uma viagem e retorna as solicitações para status Pendente"""
    try:
        data = request.get_json()
        motivo = data.get('motivo', '')

        if not motivo:
            return jsonify({'success': False, 'message': 'Motivo do cancelamento é obrigatório'}), 400

        # Busca viagem
        viagem = Viagem.query.get_or_404(viagem_id)

        # Verifica se a viagem pode ser cancelada
        if viagem.status in ['Finalizada', 'Cancelada']:
            return jsonify({'success': False, 'message': 'Esta viagem não pode ser cancelada'}), 400

        # Atualiza status da viagem
        viagem.status = 'Cancelada'
        viagem.motivo_cancelamento = motivo
        viagem.data_cancelamento = datetime.now()
        viagem.data_atualizacao = datetime.now()

        # Retorna solicitações para status Pendente
        solicitacoes = Solicitacao.query.filter_by(viagem_id=viagem_id).all()
        for solicitacao in solicitacoes:
            solicitacao.status = 'Pendente'
            solicitacao.viagem_id = None

        db.session.commit()

        flash(
            f'Viagem #{viagem.id} cancelada. {len(solicitacoes)} solicitações retornaram para status Pendente.', 'warning')
        return jsonify({
            'success': True,
            'message': f'Viagem cancelada com sucesso. {len(solicitacoes)} solicitações retornaram para Pendente.'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ===========================================================================================
# ROTAS DE HORA PARADA
# ===========================================================================================

@admin_bp.route('/viagens/<int:viagem_id>/hora-parada', methods=['GET'])
@login_required
@permission_required(['admin'])
def viagem_hora_parada_form(viagem_id):
    """
    Exibe o formulário (modal) para adicionar/editar hora parada em uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada
        import math

        # Busca a viagem
        viagem = Viagem.query.get_or_404(viagem_id)

        # Verifica se a viagem está finalizada
        if viagem.status != 'Finalizada':
            return jsonify({
                'success': False,
                'message': 'Hora parada só pode ser adicionada em viagens finalizadas.'
            }), 400

        # Verifica se já existe hora parada cadastrada
        hora_parada_existente = ViagemHoraParada.query.filter_by(
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
@permission_required(['admin'])
def viagem_hora_parada_salvar(viagem_id):
    """
    Salva (cria ou atualiza) a hora parada de uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada

        # Busca a viagem
        viagem = Viagem.query.get_or_404(viagem_id)

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
        hora_parada = ViagemHoraParada.query.filter_by(
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
                created_by_user_id=current_user.id
            )
            db.session.add(hora_parada)
            mensagem = f'Hora parada adicionada à viagem #{viagem.id} com sucesso!'

        db.session.commit()

        flash(mensagem, 'success')
        return jsonify({
            'success': True,
            'message': mensagem,
            'valor_adicional': float(valor_adicional),
            'repasse_adicional': float(repasse_adicional)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/hora-parada', methods=['DELETE'])
@login_required
@permission_required(['admin'])
def viagem_hora_parada_excluir(viagem_id):
    """
    Exclui a hora parada de uma viagem.
    Apenas Admin tem acesso.
    """
    try:
        from ..models import ViagemHoraParada

        # Busca a hora parada
        hora_parada = ViagemHoraParada.query.filter_by(
            viagem_id=viagem_id).first()

        if not hora_parada:
            return jsonify({
                'success': False,
                'message': 'Hora parada não encontrada para esta viagem.'
            }), 404

        db.session.delete(hora_parada)
        db.session.commit()

        flash(
            f'Hora parada da viagem #{viagem_id} excluída com sucesso!', 'success')
        return jsonify({
            'success': True,
            'message': 'Hora parada excluída com sucesso!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ===========================================================================================
# FIM DAS ROTAS DE HORA PARADA
# ===========================================================================================
