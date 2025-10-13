"""
Módulo de Viagens
=================

Gestão de viagens.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func, or_
from io import StringIO
import io
import csv

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp

# Importação do serviço de WhatsApp
from .whatsapp import enviar_notificacao_viagem_aceita


@admin_bp.route('/viagens')
@login_required
@permission_required(['admin', 'supervisor'])
def viagens():
    """Lista e filtra viagens criadas no sistema"""
    try:
        # Busca base de viagens
        query = Viagem.query
        
        # Aplica filtros
        filtro_viagem_id = request.args.get('viagem_id', '')
        if filtro_viagem_id:
            query = query.filter(Viagem.id == int(filtro_viagem_id))
        
        filtro_status = request.args.get('status', '')
        if filtro_status:
            query = query.filter(Viagem.status == filtro_status)
        
        filtro_data_inicio = request.args.get('data_inicio', '')
        if filtro_data_inicio:
            data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d')
            query = query.filter(
                or_(
                    Viagem.horario_entrada >= data_inicio,
                    Viagem.horario_saida >= data_inicio,
                    Viagem.horario_desligamento >= data_inicio
                )
            )
        
        filtro_data_fim = request.args.get('data_fim', '')
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
            query = query.filter(Viagem.motorista_id == int(filtro_motorista_id))
        
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
        status_opcoes = ['Pendente', 'Agendada', 'Em Andamento', 'Finalizada', 'Cancelada']
        
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
@permission_required(['admin', 'supervisor'])
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
                'veiculo_placa': viagem.motorista.veiculo_placa or 'N/A',
                'veiculo_modelo': viagem.motorista.veiculo_modelo or 'N/A'
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
                    'bairro': s.colaborador.bairro.nome if s.colaborador.bairro else 'N/A',
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
        print(f"Erro ao buscar detalhes da viagem {viagem_id}: {error_details}")
        return jsonify({'success': False, 'message': f'Erro ao carregar detalhes: {str(e)}'}), 500


@admin_bp.route('/motoristas_disponiveis')
@login_required
@permission_required(['admin', 'supervisor'])
def motoristas_disponiveis():
    """Retorna lista de motoristas disponíveis para associação"""
    try:
        motoristas = Motorista.query.filter_by(status='Ativo').order_by(Motorista.nome).all()
        
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
        # Envia notificação WhatsApp para colaboradores
        try:
            resultados_whatsapp = enviar_notificacao_viagem_aceita(viagem)
            from flask import current_app
            current_app.logger.info(f"WhatsApp enviado para {len(resultados_whatsapp)} colaboradores (associação admin)")
        except Exception as e:
            # Não interrompe o fluxo se o WhatsApp falhar
            from flask import current_app
            current_app.logger.error(f"Erro ao enviar WhatsApp: {str(e)}")
        # ========== INTEGRAÇÃO WHATSAPP - FIM ==========
        
        flash(f'Motorista {motorista.nome} associado à viagem #{viagem.id} com sucesso!', 'success')
        return jsonify({'success': True, 'message': 'Motorista associado com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/viagens/<int:viagem_id>/cancelar', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
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
        
        flash(f'Viagem #{viagem.id} cancelada. {len(solicitacoes)} solicitações retornaram para status Pendente.', 'warning')
        return jsonify({
            'success': True, 
            'message': f'Viagem cancelada com sucesso. {len(solicitacoes)} solicitações retornaram para Pendente.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

