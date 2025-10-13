#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blueprint do Motorista - Versão Aprimorada
==========================================

Rotas e funcionalidades para motoristas gerenciarem suas viagens
com a nova estrutura de Viagem completa.

Funcionalidades:
- Listar viagens disponíveis (status='Pendente')
- Listar minhas viagens (aceitas, em andamento)
- Aceitar viagem
- Cancelar viagem aceita
- Iniciar viagem
- Finalizar viagem

Autor: Sistema DOUG Moving
Data: 2025
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_, or_

from .. import db
from app.models import Viagem, Motorista, Solicitacao, Colaborador, User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro
from ..decorators import role_required

# Importação condicional de notificações
try:
    from ..utils.notificacoes import (  # type: ignore
        notificar_viagem_aceita,
        notificar_viagem_cancelada,
        notificar_viagem_finalizada
    )
    NOTIFICACOES_DISPONIVEIS = True
except ImportError:
    NOTIFICACOES_DISPONIVEIS = False

# Importação do sistema de auditoria
from ..utils.admin_audit import (
    log_viagem_audit,
    log_audit,
    AuditAction,
    get_changes_dict
)

# Importação do serviço de WhatsApp
from .whatsapp import enviar_notificacao_viagem_aceita


# CORREÇÃO: Nome do blueprint deve ser 'motorista_bp' para coincidir com __init__.py
motorista_bp = Blueprint('motorista', __name__, url_prefix='/motorista')


# =============================================================================
# ROTAS DE VISUALIZAÇÃO
# =============================================================================

@motorista_bp.route('/dashboard')
@login_required
@role_required('motorista')
def dashboard_motorista():
    """Dashboard principal do motorista."""
    
    motorista = current_user.motorista

    # Verifica se o perfil de motorista existe
    if not motorista:
        flash('Perfil de motorista não encontrado. Entre em contato com o administrador.', 'danger')
        return redirect(url_for('auth.logout'))
    
    motorista_id = motorista.id
    
    # Estatísticas
    viagens_agendadas = Viagem.query.filter_by(
        motorista_id=motorista.id,
        status='Agendada'
    ).count()
    
    viagens_em_andamento = Viagem.query.filter_by(
        motorista_id=motorista.id,
        status='Em Andamento'
    ).count()
    
    viagens_finalizadas_mes = Viagem.query.filter(
        and_(
            Viagem.motorista_id == motorista.id,
            Viagem.status == 'Finalizada',
            db.func.strftime('%Y-%m', Viagem.data_finalizacao) == datetime.now().strftime('%Y-%m')
        )
    ).count()
    
    # Viagens disponíveis (Pendente, sem motorista)
    viagens_disponiveis = Viagem.query.filter_by(
        status='Pendente',
        motorista_id=None
    ).order_by(Viagem.data_criacao.desc()).limit(10).all()
    
    # Minhas próximas viagens
    minhas_viagens = Viagem.query.filter(
        and_(
            Viagem.motorista_id == motorista.id,
            Viagem.status.in_(['Agendada', 'Em Andamento'])
        )
    ).order_by(Viagem.horario_entrada).all()
    
    return render_template(
        'motorista/dashboard_motorista.html',
        motorista=motorista,
        viagens_agendadas=viagens_agendadas,
        viagens_em_andamento=viagens_em_andamento,
        viagens_finalizadas_mes=viagens_finalizadas_mes,
        viagens_disponiveis=viagens_disponiveis,
        minhas_viagens=minhas_viagens
    )


@motorista_bp.route('/viagens/disponiveis')
@login_required
@role_required('motorista')
def viagens_disponiveis():
    """Lista todas as viagens disponíveis para aceite."""
    
    viagens = Viagem.query.filter_by(
        status='Pendente',
        motorista_id=None
    ).order_by(Viagem.data_criacao.desc()).all()
    
    return render_template(
        'motorista/viagens_disponiveis.html',
        viagens=viagens
    )



@motorista_bp.route('/viagens/<int:viagem_id>')
@login_required
@role_required('motorista')
def detalhes_viagem(viagem_id):
    """Exibe detalhes de uma viagem."""
    
    motorista = current_user.motorista
    
    viagem = Viagem.query.get_or_404(viagem_id)
    
    # Verifica se o motorista tem permissão para ver esta viagem
    if viagem.motorista_id and viagem.motorista_id != motorista.id:
        flash('Você não tem permissão para visualizar esta viagem.', 'error')
        return redirect(url_for('motorista.dashboard_motorista'))
    
    # Busca os colaboradores da viagem usando o campo colaboradores_ids
    colaboradores = []
    if viagem.colaboradores_ids:
        try:
            import json
            # Converte a string JSON para lista de IDs
            ids_lista = json.loads(viagem.colaboradores_ids)
            # Busca os colaboradores pelos IDs
            colaboradores = Colaborador.query.filter(Colaborador.id.in_(ids_lista)).all()
        except:
            # Se der erro no JSON, tenta split por vírgula
            try:
                ids_lista = [int(x.strip()) for x in viagem.colaboradores_ids.strip('[]').split(',') if x.strip()]
                colaboradores = Colaborador.query.filter(Colaborador.id.in_(ids_lista)).all()
            except:
                colaboradores = []
    
    return render_template(
        'motorista/detalhes_viagem.html',
        viagem=viagem,
        colaboradores=colaboradores
    )


# =============================================================================
# ROTAS DE AÇÃO
# =============================================================================

@motorista_bp.route('/viagens/<int:viagem_id>/aceitar', methods=['POST'])
@login_required
@role_required('motorista')
def aceitar_viagem(viagem_id):
    """Aceita uma viagem disponível."""
    
    motorista = current_user.motorista
    viagem = Viagem.query.get_or_404(viagem_id)
    
    # Verifica se a viagem pode ser aceita
    if not viagem.pode_ser_aceita():
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não está disponível para aceite.'
        }), 400
    
    # Verifica se o motorista tem veículo cadastrado
    if not motorista.veiculo_placa:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você precisa ter um veículo cadastrado para aceitar viagens.'
        }), 400
    
    # Verifica se o motorista já tem outra viagem no mesmo horário
    horario_viagem = viagem.horario_entrada or viagem.horario_saida
    if horario_viagem:
        conflito = Viagem.query.filter(
            and_(
                Viagem.motorista_id == motorista.id,
                Viagem.status.in_(['Agendada', 'Em Andamento']),
                or_(
                    Viagem.horario_entrada == horario_viagem,
                    Viagem.horario_saida == horario_viagem
                )
            )
        ).first()
        
        if conflito:
            return jsonify({
                'sucesso': False,
                'mensagem': f'Você já tem uma viagem agendada para este horário (Viagem #{conflito.id}).'
            }), 400
    
    try:
        # Aceita a viagem
        sucesso = viagem.aceitar_viagem(motorista)
        
        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível aceitar a viagem.'
            }), 400
        
        db.session.commit()
        
        # ========== INTEGRAÇÃO WHATSAPP - INÍCIO ==========
        # Envia notificação WhatsApp para colaboradores
        try:
            resultados_whatsapp = enviar_notificacao_viagem_aceita(viagem)
            from flask import current_app
            current_app.logger.info(f"WhatsApp enviado para {len(resultados_whatsapp)} colaboradores")
        except Exception as e:
            # Não interrompe o fluxo se o WhatsApp falhar
            from flask import current_app
            current_app.logger.error(f"Erro ao enviar WhatsApp: {str(e)}")
        # ========== INTEGRAÇÃO WHATSAPP - FIM ==========
        
        # Registra no log de auditoria
        log_viagem_audit(
            viagem_id=viagem.id,
            action=AuditAction.VIAGEM_ACEITA,
            motorista_id=motorista.id,
            motorista_nome=motorista.nome,
            status_anterior='Pendente',
            status_novo='Agendada',
            changes={
                'motorista_id': {'before': None, 'after': motorista.id},
                'nome_motorista': {'before': None, 'after': motorista.nome},
                'placa_veiculo': {'before': None, 'after': motorista.veiculo_placa}
            }
        )
        
        # Envia notificação para o supervisor (se módulo disponível)
        if NOTIFICACOES_DISPONIVEIS:
            # TODO: Buscar email do supervisor responsável
            # notificar_viagem_aceita(viagem, 'supervisor@empresa.com')
            pass
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Viagem #{viagem.id} aceita com sucesso!',
            'viagem_id': viagem.id
        })
        
    except Exception as e:
        db.session.rollback()
        
        # Registra erro no log
        log_audit(
            action=AuditAction.VIAGEM_ACEITA,
            resource_type='Viagem',
            resource_id=viagem.id,
            status='ERROR',
            error_message=str(e),
            severity='ERROR'
        )
        
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao aceitar viagem: {str(e)}'
        }), 500


@motorista_bp.route('/viagens/<int:viagem_id>/cancelar', methods=['POST'])
@login_required
@role_required('motorista')
def cancelar_viagem(viagem_id):
    """Desassocia o motorista da viagem, tornando-a disponível novamente."""
    
    motorista = current_user.motorista
    viagem = Viagem.query.get_or_404(viagem_id)
    
    # Verifica se o motorista é o dono da viagem
    if viagem.motorista_id != motorista.id:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não tem permissão para cancelar esta viagem.'
        }), 403
    
    # Verifica se a viagem está no status correto (Agendada)
    if viagem.status != 'Agendada':
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não pode ser cancelada. Apenas viagens agendadas (não iniciadas) podem ser canceladas.'
        }), 400
    
    try:
        # Obtém o motivo do cancelamento do request
        data = request.get_json() or {}
        motivo = data.get('motivo', 'Não informado')
        
        # Guarda informações antes da desassociação
        motorista_nome_anterior = viagem.nome_motorista
        placa_anterior = viagem.placa_veiculo
        
        # Desassocia o motorista (não cancela a viagem, apenas libera para outro motorista)
        sucesso = viagem.desassociar_motorista()
        
        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível cancelar a viagem.'
            }), 400
        
        db.session.commit()
        
        # Registra no log de auditoria com o motivo
        log_viagem_audit(
            viagem_id=viagem.id,
            action=AuditAction.MOTORISTA_DESASSOCIADO,
            motorista_id=motorista.id,
            motorista_nome=motorista.nome,
            status_anterior='Agendada',
            status_novo='Pendente',
            changes={
                'motorista_id': {'before': motorista.id, 'after': None},
                'nome_motorista': {'before': motorista_nome_anterior, 'after': None},
                'placa_veiculo': {'before': placa_anterior, 'after': None}
            },
            reason=motivo  # AQUI É ONDE O MOTIVO É GUARDADO!
        )
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Você foi desassociado da viagem #{viagem.id}. A viagem está disponível novamente para outros motoristas.',
            'viagem_id': viagem.id
        })
        
    except Exception as e:
        db.session.rollback()
        
        # Registra erro no log
        log_audit(
            action=AuditAction.MOTORISTA_DESASSOCIADO,
            resource_type='Viagem',
            resource_id=viagem.id,
            status='ERROR',
            error_message=str(e),
            severity='ERROR'
        )
        
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao cancelar viagem: {str(e)}'
        }), 500


@motorista_bp.route('/viagens/<int:viagem_id>/iniciar', methods=['POST'])
@login_required
@role_required('motorista')
def iniciar_viagem(viagem_id):
    """Inicia uma viagem agendada."""
    
    motorista = current_user.motorista
    motorista_id = motorista.id  # ← ADICIONAR ESTA LINHA
    viagem = Viagem.query.get_or_404(viagem_id)
    
    # Verifica se o motorista é o dono da viagem
    if viagem.motorista_id != motorista.id:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não tem permissão para iniciar esta viagem.'
        }), 403
    
    # Verifica se a viagem pode ser iniciada
    if not viagem.pode_ser_iniciada(motorista_id):
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não pode ser iniciada (status incorreto).'
        }), 400
    
    try:
        # Inicia a viagem
        sucesso = viagem.iniciar_viagem(motorista_id)
        
        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível iniciar a viagem.'
            }), 400
        
        db.session.commit()
        
        # Registra no log de auditoria
        log_viagem_audit(
            viagem_id=viagem.id,
            action=AuditAction.VIAGEM_INICIADA,
            motorista_id=motorista.id,
            motorista_nome=motorista.nome,
            status_anterior='Agendada',
            status_novo='Em Andamento'
        )
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Viagem #{viagem.id} iniciada com sucesso!',
            'viagem_id': viagem.id
        })
        
    except Exception as e:
        db.session.rollback()
        
        # Registra erro no log
        log_audit(
            action=AuditAction.VIAGEM_INICIADA,
            resource_type='Viagem',
            resource_id=viagem.id,
            status='ERROR',
            error_message=str(e),
            severity='ERROR'
        )
        
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao iniciar viagem: {str(e)}'
        }), 500


@motorista_bp.route('/viagens/<int:viagem_id>/finalizar', methods=['POST'])
@login_required
@role_required('motorista')
def finalizar_viagem(viagem_id):
    """Finaliza uma viagem em andamento."""
    
    motorista = current_user.motorista
    motorista_id = motorista.id  # ← ADICIONAR ESTA LINHA
    viagem = Viagem.query.get_or_404(viagem_id)
    
    # Verifica se o motorista é o dono da viagem
    if viagem.motorista_id != motorista.id:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não tem permissão para finalizar esta viagem.'
        }), 403
    
    # Verifica se a viagem pode ser finalizada
    if not viagem.pode_ser_finalizada(motorista_id):
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não pode ser finalizada (não está em andamento).'
        }), 400
    
    try:
        # Finaliza a viagem
        sucesso = viagem.finalizar_viagem(motorista_id)
        
        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível finalizar a viagem.'
            }), 400
        
        db.session.commit()
        
        # Registra no log de auditoria
        log_viagem_audit(
            viagem_id=viagem.id,
            action=AuditAction.VIAGEM_FINALIZADA,
            motorista_id=motorista.id,
            motorista_nome=motorista.nome,
            status_anterior='Em Andamento',
            status_novo='Finalizada',
            valor_repasse_novo=float(viagem.valor_repasse) if viagem.valor_repasse else 0
        )
        
        # Envia notificação (se módulo disponível)
        if NOTIFICACOES_DISPONIVEIS:
            # TODO: Buscar email do supervisor
            # notificar_viagem_finalizada(viagem, 'supervisor@empresa.com')
            pass
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Viagem #{viagem.id} finalizada com sucesso!',
            'viagem_id': viagem.id,
            'valor_repasse': float(viagem.valor_repasse) if viagem.valor_repasse else 0
        })
        
    except Exception as e:
        db.session.rollback()
        
        # Registra erro no log
        log_audit(
            action=AuditAction.VIAGEM_FINALIZADA,
            resource_type='Viagem',
            resource_id=viagem.id,
            status='ERROR',
            error_message=str(e),
            severity='ERROR'
        )
        
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao finalizar viagem: {str(e)}'
        }), 500


# =============================================================================
# ROTAS DE API (JSON)
# =============================================================================

@motorista_bp.route('/api/viagens/disponiveis')
@login_required
@role_required('motorista')
def api_viagens_disponiveis():
    """API: Retorna viagens disponíveis em formato JSON."""
    
    viagens = Viagem.query.filter_by(
        status='Pendente',
        motorista_id=None
    ).order_by(Viagem.data_criacao.desc()).all()
    
    return jsonify({
        'sucesso': True,
        'viagens': [
            {
                'id': v.id,
                'tipo_corrida': v.tipo_corrida,
                'quantidade_passageiros': v.quantidade_passageiros,
                'horario_entrada': v.horario_entrada,
                'horario_saida': v.horario_saida,
                'blocos_ids': v.blocos_ids,
                'valor': float(v.valor) if v.valor else 0,
                'valor_repasse': float(v.valor_repasse) if v.valor_repasse else 0
            }
            for v in viagens
        ]
    })


@motorista_bp.route('/api/viagens/minhas')
@login_required
@role_required('motorista')
def api_minhas_viagens():
    """API: Retorna viagens do motorista em formato JSON."""
    
    motorista = current_user.motorista
    status_filtro = request.args.get('status')
    
    query = Viagem.query.filter_by(motorista_id=motorista.id)
    
    if status_filtro:
        query = query.filter_by(status=status_filtro)
    
    viagens = query.order_by(Viagem.data_criacao.desc()).all()
    
    return jsonify({
        'sucesso': True,
        'viagens': [
            {
                'id': v.id,
                'status': v.status,
                'tipo_corrida': v.tipo_corrida,
                'quantidade_passageiros': v.quantidade_passageiros,
                'horario_entrada': v.horario_entrada,
                'horario_saida': v.horario_saida,
                'blocos_ids': v.blocos_ids,
                'valor_repasse': float(v.valor_repasse) if v.valor_repasse else 0,
                'data_criacao': v.data_criacao.isoformat() if v.data_criacao else None
            }
            for v in viagens
        ]
    })

# ============================================================================
# ROTA: MINHAS VIAGENS (Histórico do Motorista)
# ============================================================================
# 
# Adicionar esta rota no arquivo: app/blueprints/motorista.py
# Adicionar após a rota de dashboard_motorista
# 

@motorista_bp.route('/viagens')
@login_required
@role_required('motorista')
def minhas_viagens():
    """Lista todas as viagens do motorista com filtros."""
    
    motorista = current_user.motorista
    
    # Verifica se o perfil de motorista existe
    if not motorista:
        flash('Perfil de motorista não encontrado. Entre em contato com o administrador.', 'danger')
        return redirect(url_for('auth.logout'))
    
    motorista_id = motorista.id
    
    try:
        # Busca base de viagens (apenas do motorista logado)
        query = Viagem.query.filter(Viagem.motorista_id == motorista_id)
        
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
        
        filtro_bloco_id = request.args.get('bloco_id', '')
        if filtro_bloco_id:
            query = query.filter(Viagem.bloco_id == int(filtro_bloco_id))
        
        filtro_planta_id = request.args.get('planta_id', '')
        if filtro_planta_id:
            query = query.filter(Viagem.planta_id == int(filtro_planta_id))
        
        filtro_empresa_id = request.args.get('empresa_id', '')
        if filtro_empresa_id:
            query = query.filter(Viagem.empresa_id == int(filtro_empresa_id))
        
        # Ordena por data/horário mais recente
        viagens = query.order_by(Viagem.id.desc()).all()
        
        # Calcula o total de repasse APENAS das viagens finalizadas
        total_repasse = sum(v.valor_repasse or 0 for v in viagens if v.status == 'Finalizada')
        
        # Busca dados para os filtros
        blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
        plantas = Planta.query.order_by(Planta.nome).all()
        empresas = Empresa.query.order_by(Empresa.nome).all()
        
        # Opções de status
        status_opcoes = ['Pendente', 'Agendada', 'Em Andamento', 'Finalizada', 'Cancelada']
        
        return render_template(
            'motorista/viagens_motorista.html',
            viagens=viagens,
            blocos=blocos,
            plantas=plantas,
            empresas=empresas,
            status_opcoes=status_opcoes,
            total_repasse=total_repasse,
            filtro_viagem_id=filtro_viagem_id,
            filtro_status=filtro_status,
            filtro_data_inicio=filtro_data_inicio,
            filtro_data_fim=filtro_data_fim,
            filtro_bloco_id=filtro_bloco_id,
            filtro_planta_id=filtro_planta_id,
            filtro_empresa_id=filtro_empresa_id
        )
        
    except Exception as e:
        flash(f'Erro ao carregar viagens: {str(e)}', 'danger')
        return redirect(url_for('motorista.dashboard_motorista'))





@motorista_bp.route('/toggle-disponibilidade', methods=['POST'])
@login_required
@role_required('motorista')
def toggle_disponibilidade():
    """Alterna o status de disponibilidade do motorista (online/offline)."""
    
    motorista = current_user.motorista
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Perfil de motorista não encontrado.'
        }), 404
    
    try:
        # Alterna o status
        if motorista.status_disponibilidade == 'online':
            motorista.status_disponibilidade = 'offline'
            mensagem = 'Você está agora OFFLINE. Não receberá novas viagens.'
        else:
            motorista.status_disponibilidade = 'online'
            mensagem = 'Você está agora ONLINE. Pode aceitar novas viagens.'
        
        db.session.commit()
        
        return jsonify({
            'sucesso': True,
            'mensagem': mensagem,
            'status_atual': motorista.status_disponibilidade
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao alterar disponibilidade: {str(e)}'
        }), 500

