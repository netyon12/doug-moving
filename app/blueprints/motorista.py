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

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import and_, or_

from .. import db
from ..config.tenant_utils import query_tenant, get_tenant_session, get_or_404_tenant, paginate_tenant
from ..models import Viagem, Motorista, Solicitacao, Colaborador, User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro
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

# Importação do serviço de notificações
from app.services.notification_service import notification_service


# CORREÇÃO: Nome do blueprint deve ser 'motorista_bp' para coincidir com __init__.py
motorista_bp = Blueprint('motorista', __name__, url_prefix='/motorista')


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_database_type():
    """
    Detecta qual banco de dados está sendo usado.
    Retorna 'sqlite' ou 'postgresql'.
    """
    database_url = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if 'postgresql' in database_url or 'postgres' in database_url:
        return 'postgresql'
    else:
        return 'sqlite'


def get_motorista_tenant():
    """
    Busca o motorista no banco correto (tenant) baseado no CPF.
    
    Em ambiente multi-tenant, o motorista pode ter IDs diferentes em cada banco.
    Esta função garante que sempre usaremos o ID correto do banco ativo.
    
    Returns:
        Motorista: Objeto motorista do banco tenant
        None: Se motorista não encontrado
    
    Raises:
        Exception: Se current_user não tem perfil de motorista
    """
    motorista_base = current_user.motorista
    
    if not motorista_base:
        raise Exception('Perfil de motorista não encontrado')
    
    # Buscar motorista no banco tenant por CPF (chave única)
    # Força refresh do banco para evitar cache
    session = get_tenant_session()
    motorista_tenant = session.query(Motorista).filter_by(
        cpf_cnpj=motorista_base.cpf_cnpj
    ).first()
    
    # Força refresh dos dados do banco
    if motorista_tenant:
        session.refresh(motorista_tenant)
    
    return motorista_tenant


# =============================================================================
# ROTAS DE VISUALIZAÇÃO
# =============================================================================

@motorista_bp.route('/dashboard')
@login_required
@role_required('motorista')
def dashboard_motorista():
    """Dashboard principal do motorista."""

    # Buscar motorista no banco correto (tenant)
    motorista = get_motorista_tenant()
    
    if not motorista:
        flash('Seu cadastro não foi encontrado nesta empresa. Entre em contato com o administrador.', 'warning')
        return redirect(url_for('auth.logout'))

    # Estatísticas
    viagens_agendadas = query_tenant(Viagem).filter_by(
        motorista_id=motorista.id,
        status='Agendada'
    ).count()

    viagens_em_andamento = query_tenant(Viagem).filter_by(
        motorista_id=motorista.id,
        status='Em Andamento'
    ).count()

    # Consulta compatível com SQLite e PostgreSQL
    mes_atual = datetime.now().strftime('%Y-%m')

    # Detecta o banco de dados e usa a função apropriada
    db_type = get_database_type()

    if db_type == 'postgresql':
        # PostgreSQL usa to_char
        viagens_finalizadas_mes = query_tenant(Viagem).filter(
            and_(
                Viagem.motorista_id == motorista.id,
                Viagem.status == 'Finalizada',
                db.func.to_char(Viagem.data_finalizacao,
                                'YYYY-MM') == mes_atual
            )
        ).count()
    else:
        # SQLite usa strftime
        viagens_finalizadas_mes = query_tenant(Viagem).filter(
            and_(
                Viagem.motorista_id == motorista.id,
                Viagem.status == 'Finalizada',
                db.func.strftime('%Y-%m', Viagem.data_finalizacao) == mes_atual
            )
        ).count()

    # Viagens disponíveis (Pendente, sem motorista) - limit(30) - quantidade de viagens aparece na tela
    viagens_disponiveis = query_tenant(Viagem).filter_by(
        status='Pendente',
        motorista_id=None
    ).order_by(Viagem.data_criacao.desc()).limit(30).all()

    # Minhas próximas viagens
    minhas_viagens = query_tenant(Viagem).filter(
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

    viagens = query_tenant(Viagem).filter_by(
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

    motorista = get_motorista_tenant()
    
    if not motorista:
        flash('Seu cadastro não foi encontrado nesta empresa.', 'warning')
        return redirect(url_for('motorista.dashboard_motorista'))

    viagem = get_or_404_tenant(Viagem, viagem_id)

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
            colaboradores = query_tenant(Colaborador).filter(
                Colaborador.id.in_(ids_lista)).all()
        except:
            # Se der erro no JSON, tenta split por vírgula
            try:
                ids_lista = [int(x.strip()) for x in viagem.colaboradores_ids.strip(
                    '[]').split(',') if x.strip()]
                colaboradores = query_tenant(Colaborador).filter(
                    Colaborador.id.in_(ids_lista)).all()
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

    motorista = get_motorista_tenant()
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Seu cadastro não foi encontrado nesta empresa. Entre em contato com o administrador.'
        }), 403
    
    viagem = get_or_404_tenant(Viagem, viagem_id)

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
        conflito = query_tenant(Viagem).filter(
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
        # Aceita a viagem (motorista já é do banco correto)
        sucesso = viagem.aceitar_viagem(motorista)

        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível aceitar a viagem.'
            }), 400

        get_tenant_session().commit()

        # ✅ LOG no Terminal (APÓS commit)
        num_passageiros = len(
            viagem.solicitacoes) if viagem.solicitacoes else 0
        current_app.logger.info(
            f"✅ VIAGEM ACEITA: ID={viagem.id}, "
            f"Motorista={motorista.nome}, "
            f"Passageiros={num_passageiros}, "
            f"Bloco={viagem.bloco.codigo_bloco if viagem.bloco else 'N/A'}, "
            f"Data={viagem.data_inicio}"
        )

        # ========== INTEGRAÇÃO WHATSAPP - INÍCIO ==========
        # Envia notificação WhatsApp para colaboradores (exceto Desligamento)
        if viagem.tipo_corrida != 'desligamento':
            try:
                sucesso = notification_service.notificar_viagem_confirmada(
                    viagem_id=viagem.id,
                    motorista_id=motorista.id
                )
                if sucesso:
                    flash('Viagem aceita! Notificações enviadas.', 'success')
                else:
                    flash('Viagem aceita com sucesso!', 'success')
            except Exception as e:
                current_app.logger.error(f'Erro WhatsApp: {e}')
                flash('Viagem aceita com sucesso!', 'success')
        else:
            flash('Viagem aceita com sucesso!', 'success')

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
        get_tenant_session().rollback()
        current_app.logger.error(
            f"❌ ERRO ao aceitar viagem {viagem_id}: {str(e)}")
        flash('Erro ao aceitar viagem', 'danger')

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
            'mensagem': f'❌ ERRO ao aceitar viagem: {str(e)}'
        }), 500


@motorista_bp.route('/viagens/<int:viagem_id>/cancelar', methods=['POST'])
@login_required
@role_required('motorista')
def cancelar_viagem(viagem_id):
    """Desassocia o motorista da viagem, tornando-a disponível novamente."""

    motorista = get_motorista_tenant()
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Seu cadastro não foi encontrado nesta empresa.'
        }), 403
    
    viagem = get_or_404_tenant(Viagem, viagem_id)

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

        get_tenant_session().commit()

        # Notifica colaboradores sobre cancelamento (exceto Desligamento)
        if viagem.tipo_corrida != 'desligamento':
            try:
                enviadas = notification_service.notificar_viagem_cancelada_por_motorista(
                    viagem, motivo)
                if enviadas > 0:
                    current_app.logger.info(
                        f"Viagem #{viagem.id} cancelada: {enviadas} colaboradores notificados")
            except Exception as e:
                current_app.logger.error(
                    f"Erro ao notificar colaboradores sobre cancelamento da viagem #{viagem.id}: {e}")
                # Não interrompe o processo se notificação falhar

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
        get_tenant_session().rollback()

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

    motorista = get_motorista_tenant()
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Seu cadastro não foi encontrado nesta empresa.'
        }), 403
    
    viagem = get_or_404_tenant(Viagem, viagem_id)

    # Verifica se o motorista é o dono da viagem
    if viagem.motorista_id != motorista.id:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não tem permissão para iniciar esta viagem.'
        }), 403

    # VALIDAÇÃO: Verifica se o motorista já tem outra viagem EM ANDAMENTO
    # (Motorista não pode dirigir duas corridas ao mesmo tempo)
    viagem_em_andamento = query_tenant(Viagem).filter(
        and_(
            Viagem.motorista_id == motorista.id,
            Viagem.status == 'Em Andamento',
            Viagem.id != viagem_id  # Exclui a própria viagem
        )
    ).first()

    if viagem_em_andamento:
        return jsonify({
            'sucesso': False,
            'mensagem': f'Você já tem uma viagem em andamento (Viagem #{viagem_em_andamento.id}). Finalize a viagem atual antes de iniciar uma nova.'
        }), 400

    # Verifica se a viagem pode ser iniciada
    if not viagem.pode_ser_iniciada(motorista.id):
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não pode ser iniciada (status incorreto).'
        }), 400

    try:
        # Inicia a viagem
        sucesso = viagem.iniciar_viagem(motorista.id)

        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível iniciar a viagem.'
            }), 400

        get_tenant_session().commit()

        # ✅ LOG no Terminal (APÓS commit)
        current_app.logger.info(
            f"✅ VIAGEM Iniciada! "
        )

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
        get_tenant_session().rollback()

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

    motorista = get_motorista_tenant()
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Seu cadastro não foi encontrado nesta empresa.'
        }), 403
    
    viagem = get_or_404_tenant(Viagem, viagem_id)

    # Verifica se o motorista é o dono da viagem
    if viagem.motorista_id != motorista.id:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não tem permissão para finalizar esta viagem.'
        }), 403

    # Verifica se a viagem pode ser finalizada
    if not viagem.pode_ser_finalizada(motorista.id):
        return jsonify({
            'sucesso': False,
            'mensagem': 'Esta viagem não pode ser finalizada (não está em andamento).'
        }), 400

    try:
        # Finaliza a viagem
        sucesso = viagem.finalizar_viagem(motorista.id)

        if not sucesso:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Não foi possível finalizar a viagem.'
            }), 400

        get_tenant_session().commit()

        # ✅ LOG no Terminal (APÓS commit)
        duracao = viagem.data_finalizacao - \
            viagem.data_inicio if viagem.data_finalizacao and viagem.data_inicio else 'N/A'
        num_passageiros = len(
            viagem.solicitacoes) if viagem.solicitacoes else 0
        current_app.logger.info(
            f"✅ VIAGEM FINALIZADA: ID={viagem.id}, "
            f"Motorista={motorista.nome}, "
            f"Passageiros={num_passageiros}, "
            f"Duração={duracao}, "
            f"Bloco={viagem.bloco.codigo_bloco if viagem.bloco else 'N/A'}"
        )

        # Registra no log de auditoria
        log_viagem_audit(
            viagem_id=viagem.id,
            action=AuditAction.VIAGEM_FINALIZADA,
            motorista_id=motorista.id,
            motorista_nome=motorista.nome,
            status_anterior='Em Andamento',
            status_novo='Finalizada',
            valor_repasse_novo=float(
                viagem.valor_repasse) if viagem.valor_repasse else 0
        )

        # Envia notificação (se módulo disponível)
        if NOTIFICACOES_DISPONIVEIS:
            # TODO: Buscar email do supervisor responsável
            # notificar_viagem_finalizada(viagem, 'supervisor@empresa.com')
            pass

        return jsonify({
            'sucesso': True,
            'mensagem': f'Viagem #{viagem.id} finalizada com sucesso!',
            'viagem_id': viagem.id,
            'valor_repasse': float(viagem.valor_repasse) if viagem.valor_repasse else 0.0
        })

    except Exception as e:
        get_tenant_session().rollback()
        current_app.logger.error(
            f"❌ ERRO ao finalizar viagem {viagem_id}: {str(e)}")

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
# ROTAS DE API (PARA ATUALIZAÇÕES VIA AJAX)
# =============================================================================

@motorista_bp.route('/toggle-disponibilidade', methods=['POST'])
@login_required
@role_required('motorista')
def toggle_disponibilidade():
    """Alterna o status de disponibilidade do motorista entre online e offline."""

    motorista = get_motorista_tenant()
    
    if not motorista:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Seu cadastro não foi encontrado nesta empresa.'
        }), 403

    # Verifica se o motorista tem viagens em andamento
    viagens_em_andamento = query_tenant(Viagem).filter(
        and_(
            Viagem.motorista_id == motorista.id,
            Viagem.status == 'Em Andamento'
        )
    ).count()

    # Se tiver viagem em andamento, não pode ficar offline
    if viagens_em_andamento > 0:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não pode ficar offline enquanto tiver uma viagem em andamento. Finalize a viagem primeiro.'
        }), 400

    try:
        # Alterna entre online e offline
        if motorista.status_disponibilidade == 'online':
            motorista.status_disponibilidade = 'offline'
            mensagem = 'Você está agora OFFLINE. Não receberá novas viagens.'
        else:
            motorista.status_disponibilidade = 'online'
            mensagem = 'Você está agora ONLINE. Pode receber novas viagens.'

        get_tenant_session().commit()

        # Registra no log de auditoria
        log_audit(
            action=AuditAction.UPDATE,
            resource_type='Motorista',
            resource_id=motorista.id,
            user_id=current_user.id,
            user_name=current_user.email,
            changes={'status_disponibilidade': {'before': 'online' if motorista.status_disponibilidade ==
                                                'offline' else 'offline', 'after': motorista.status_disponibilidade}}
        )

        return jsonify({
            'sucesso': True,
            'mensagem': mensagem,
            'novo_status': motorista.status_disponibilidade
        })

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro ao alterar disponibilidade: {str(e)}'
        }), 500


@motorista_bp.route('/atualizar_status_disponibilidade', methods=['POST'])
@login_required
@role_required('motorista')
def atualizar_status_disponibilidade():
    """Atualiza o status de disponibilidade do motorista."""

    motorista = current_user.motorista
    novo_status = request.json.get('status')

    if not novo_status or novo_status not in [Motorista.STATUS_DISPONIVEL, Motorista.STATUS_INDISPONIVEL, Motorista.STATUS_AUSENTE]:
        return jsonify({'sucesso': False, 'mensagem': 'Status inválido.'}), 400

    # Não permite alterar para "Disponível" se estiver em viagem
    if novo_status == Motorista.STATUS_DISPONIVEL and motorista.status == Motorista.STATUS_EM_VIAGEM:
        return jsonify({
            'sucesso': False,
            'mensagem': 'Você não pode ficar disponível enquanto estiver em uma viagem.'
        }), 400

    # Não permite alterar se estiver em viagem
    if motorista.status == Motorista.STATUS_EM_VIAGEM:
        return jsonify({
            'sucesso': False,
            'mensagem': f'Seu status está "Em Viagem" e será atualizado automaticamente ao finalizar a viagem.'
        }), 400

    try:
        status_anterior = motorista.status
        motorista.status = novo_status
        get_tenant_session().commit()

        # Registra no log de auditoria
        log_audit(
            action=AuditAction.UPDATE,
            resource_type='Motorista',
            resource_id=motorista.id,
            user_id=current_user.id,
            user_name=current_user.email,
            changes={'status': {'before': status_anterior, 'after': novo_status}}
        )

        return jsonify({
            'sucesso': True,
            'mensagem': f'Status atualizado para "{novo_status}" com sucesso!',
            'novo_status': novo_status
        })

    except Exception as e:
        get_tenant_session().rollback()
        return jsonify({'sucesso': False, 'mensagem': f'Erro ao atualizar status: {str(e)}'}), 500


@motorista_bp.route("/minhas-viagens")
@login_required
@role_required('motorista')
def minhas_viagens():
    """Página para o motorista visualizar seu histórico de viagens."""
    motorista = get_motorista_tenant()
    
    if not motorista:
        flash('Seu cadastro não foi encontrado nesta empresa.', 'warning')
        return redirect(url_for('motorista.dashboard_motorista'))

    # Filtros
    page = request.args.get('page', 1, type=int)
    filtro_viagem_id = request.args.get('viagem_id', '')
    filtro_status = request.args.get('status', '')
    filtro_data_inicio = request.args.get('data_inicio', '')
    filtro_data_fim = request.args.get('data_fim', '')
    filtro_empresa_id = request.args.get('empresa_id', '')
    filtro_planta_id = request.args.get('planta_id', '')
    filtro_bloco_id = request.args.get('bloco_id', '')

    # Query base
    query = query_tenant(Viagem).filter_by(motorista_id=motorista.id)

    # Aplicar filtros
    if filtro_viagem_id:
        try:
            query = query.filter(Viagem.id == int(filtro_viagem_id))
        except ValueError:
            flash('ID de viagem inválido.', 'warning')

    if filtro_status:
        query = query.filter(Viagem.status == filtro_status)

    if filtro_data_inicio:
        try:
            data_inicio_obj = datetime.strptime(filtro_data_inicio, '%Y-%m-%d')
            query = query.filter(Viagem.data_criacao >= data_inicio_obj)
        except ValueError:
            flash('Formato de data de início inválido. Use AAAA-MM-DD.', 'warning')

    if filtro_data_fim:
        try:
            data_fim_obj = datetime.strptime(filtro_data_fim, '%Y-%m-%d')
            from datetime import timedelta
            query = query.filter(Viagem.data_criacao <
                                 data_fim_obj + timedelta(days=1))
        except ValueError:
            flash('Formato de data de fim inválido. Use AAAA-MM-DD.', 'warning')

    if filtro_empresa_id:
        try:
            query = query.filter(Viagem.empresa_id == int(filtro_empresa_id))
        except ValueError:
            flash('ID de empresa inválido.', 'warning')

    if filtro_planta_id:
        try:
            query = query.filter(Viagem.planta_id == int(filtro_planta_id))
        except ValueError:
            flash('ID de planta inválido.', 'warning')

    if filtro_bloco_id:
        try:
            query = query.filter(Viagem.bloco_id == int(filtro_bloco_id))
        except ValueError:
            flash('ID de bloco inválido.', 'warning')

    # Paginação
    viagens_paginadas = paginate_tenant(
        query.order_by(Viagem.data_criacao.desc()),
        page=page, per_page=15, error_out=False)

    # Calcular totais (baseado na query filtrada)
    total_viagens = query.count()
    total_repasse = get_tenant_session().query(db.func.sum(Viagem.valor_repasse)).filter(
        Viagem.motorista_id == motorista.id
    ).scalar() or 0.0

    # Buscar dados para os filtros
    status_opcoes = ['Pendente', 'Agendada',
                     'Em Andamento', 'Finalizada', 'Cancelada']
    empresas = query_tenant(Empresa).order_by(Empresa.nome).all()
    plantas = query_tenant(Planta).order_by(Planta.nome).all()
    blocos = query_tenant(Bloco).order_by(Bloco.codigo_bloco).all()

    return render_template(
        "motorista/viagens_motorista.html",
        viagens=viagens_paginadas,
        total_viagens=total_viagens,
        total_repasse=total_repasse,
        filtro_viagem_id=filtro_viagem_id,
        filtro_status=filtro_status,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim,
        filtro_empresa_id=filtro_empresa_id,
        filtro_planta_id=filtro_planta_id,
        filtro_bloco_id=filtro_bloco_id,
        status_opcoes=status_opcoes,
        empresas=empresas,
        plantas=plantas,
        blocos=blocos
    )
