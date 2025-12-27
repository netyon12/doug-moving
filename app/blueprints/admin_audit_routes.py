# -*- coding: utf-8 -*-
"""
Rotas de Auditoria para Administradores - Sistema Go Mobi
=========================================================

Rotas para visualização e análise de logs de auditoria.

Funcionalidades:
- Visualizar logs gerais do sistema
- Visualizar histórico de viagens
- Filtrar logs por diversos critérios
- Exportar relatórios
- Ver operações que falharam

Autor: Sistema DOUG Moving
Data: Outubro 2025
"""

from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc
import json
import io
import csv

from .. import db
from ..config.tenant_utils import query_tenant, paginate_tenant
from ..models import AuditLog, ViagemAuditoria, Viagem, User, Motorista
from ..decorators import role_required
from ..utils.admin_audit import (
    get_user_activity,
    get_viagem_history,
    get_recent_logs,
    get_failed_operations,
    AuditAction
)

# Blueprint
audit_bp = Blueprint('audit', __name__, url_prefix='/admin/audit')


# =============================================================================
# ROTAS DE VISUALIZAÇÃO
# =============================================================================

@audit_bp.route('/')
@login_required
@role_required('admin')
def logs_gerais():
    """Página principal de logs gerais do sistema."""
    
    # Parâmetros de filtro
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    action = request.args.get('action', '')
    resource_type = request.args.get('resource_type', '')
    user_id = request.args.get('user_id', type=int)
    severity = request.args.get('severity', '')
    status = request.args.get('status', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = query_tenant(AuditLog)
    
    # Aplica filtros
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if user_id:
        query = query.filter_by(user_id=user_id)
    if severity:
        query = query.filter_by(severity=severity)
    if status:
        query = query.filter_by(status=status)
    if data_inicio:
        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp >= dt_inicio)
        except:
            pass
    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            dt_fim = dt_fim.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.timestamp <= dt_fim)
        except:
            pass
    
    # Ordena e pagina
    logs_pagination = paginate_tenant(
        query.order_by(desc(AuditLog.timestamp)),
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Estatísticas rápidas
    total_logs = query_tenant(AuditLog).count()
    logs_hoje = query_tenant(AuditLog).filter(
        AuditLog.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
    ).count()
    logs_erro = query_tenant(AuditLog).filter(
        AuditLog.status.in_(['FAILED', 'ERROR'])
    ).count()
    
    # Lista de ações disponíveis para filtro
    acoes_disponiveis = db.session.query(AuditLog.action).distinct().all()
    acoes_disponiveis = [a[0] for a in acoes_disponiveis]
    
    # Lista de tipos de recurso para filtro
    recursos_disponiveis = db.session.query(AuditLog.resource_type).distinct().all()
    recursos_disponiveis = [r[0] for r in recursos_disponiveis]
    
    # Lista de usuários para filtro
    usuarios = User.query.all()
    
    return render_template(
        'admin/audit_logs.html',
        logs=logs_pagination.items,
        pagination=logs_pagination,
        total_logs=total_logs,
        logs_hoje=logs_hoje,
        logs_erro=logs_erro,
        acoes_disponiveis=acoes_disponiveis,
        recursos_disponiveis=recursos_disponiveis,
        usuarios=usuarios,
        filtros={
            'action': action,
            'resource_type': resource_type,
            'user_id': user_id,
            'severity': severity,
            'status': status,
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }
    )


@audit_bp.route('/viagens')
@login_required
@role_required('admin')
def logs_viagens():
    """Página de logs específicos de viagens."""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    viagem_id = request.args.get('viagem_id', type=int)
    motorista_id = request.args.get('motorista_id', type=int)
    action = request.args.get('action', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = query_tenant(ViagemAuditoria)
    
    # Aplica filtros
    if viagem_id:
        query = query.filter_by(viagem_id=viagem_id)
    if motorista_id:
        query = query.filter_by(motorista_id=motorista_id)
    if action:
        query = query.filter_by(action=action)
    if data_inicio:
        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(ViagemAuditoria.timestamp >= dt_inicio)
        except:
            pass
    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            dt_fim = dt_fim.replace(hour=23, minute=59, second=59)
            query = query.filter(ViagemAuditoria.timestamp <= dt_fim)
        except:
            pass
    
    # Ordena e pagina
    logs_pagination = paginate_tenant(
        query.order_by(desc(ViagemAuditoria.timestamp)),
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Estatísticas
    total_logs = query_tenant(ViagemAuditoria).count()
    viagens_aceitas_hoje = query_tenant(ViagemAuditoria).filter(
        and_(
            ViagemAuditoria.action == 'VIAGEM_ACEITA',
            ViagemAuditoria.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
    ).count()
    cancelamentos_hoje = query_tenant(ViagemAuditoria).filter(
        and_(
            ViagemAuditoria.action.in_(['VIAGEM_CANCELADA', 'MOTORISTA_DESASSOCIADO']),
            ViagemAuditoria.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
    ).count()
    
    # Listas para filtros
    acoes_disponiveis = db.session.query(ViagemAuditoria.action).distinct().all()
    acoes_disponiveis = [a[0] for a in acoes_disponiveis]
    
    motoristas = Motorista.query.all()
    
    return render_template(
        'admin/audit_viagens.html',
        logs=logs_pagination.items,
        pagination=logs_pagination,
        total_logs=total_logs,
        viagens_aceitas_hoje=viagens_aceitas_hoje,
        cancelamentos_hoje=cancelamentos_hoje,
        acoes_disponiveis=acoes_disponiveis,
        motoristas=motoristas,
        filtros={
            'viagem_id': viagem_id,
            'motorista_id': motorista_id,
            'action': action,
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }
    )


@audit_bp.route('/viagem/<int:viagem_id>/historico')
@login_required
@role_required('admin')
def historico_viagem(viagem_id):
    """Exibe histórico completo de uma viagem específica."""
    
    viagem = Viagem.query.get_or_404(viagem_id)
    historico = get_viagem_history(viagem_id)
    
    return render_template(
        'admin/viagem_historico.html',
        viagem=viagem,
        historico=historico
    )


@audit_bp.route('/usuario/<int:user_id>/atividades')
@login_required
@role_required('admin')
def atividades_usuario(user_id):
    """Exibe atividades de um usuário específico."""
    
    user = User.query.get_or_404(user_id)
    limit = request.args.get('limit', 100, type=int)
    
    atividades = get_user_activity(user_id, limit=limit)
    
    return render_template(
        'admin/usuario_atividades.html',
        user=user,
        atividades=atividades
    )


@audit_bp.route('/falhas')
@login_required
@role_required('admin')
def operacoes_falhadas():
    """Exibe operações que falharam."""
    
    limit = request.args.get('limit', 100, type=int)
    falhas = get_failed_operations(limit=limit)
    
    return render_template(
        'admin/audit_falhas.html',
        falhas=falhas
    )


# =============================================================================
# ROTAS DE API/AJAX
# =============================================================================

@audit_bp.route('/api/log/<int:log_id>')
@login_required
@role_required('admin')
def detalhes_log(log_id):
    """Retorna detalhes de um log específico em JSON."""
    
    log = query_tenant(AuditLog).get_or_404(log_id)
    return jsonify(log.to_dict())


@audit_bp.route('/api/viagem-audit/<int:audit_id>')
@login_required
@role_required('admin')
def detalhes_viagem_audit(audit_id):
    """Retorna detalhes de um log de viagem em JSON."""
    
    audit = query_tenant(ViagemAuditoria).get_or_404(audit_id)
    return jsonify(audit.to_dict())


@audit_bp.route('/api/estatisticas')
@login_required
@role_required('admin')
def estatisticas():
    """Retorna estatísticas gerais de auditoria."""
    
    # Período (últimos 7 dias por padrão)
    dias = request.args.get('dias', 7, type=int)
    data_inicio = datetime.utcnow() - timedelta(days=dias)
    
    # Total de logs
    total_logs = query_tenant(AuditLog).filter(
        AuditLog.timestamp >= data_inicio
    ).count()
    
    # Logs por dia
    logs_por_dia = db.session.query(
        db.func.date(AuditLog.timestamp).label('dia'),
        db.func.count(AuditLog.id).label('total')
    ).filter(
        AuditLog.timestamp >= data_inicio
    ).group_by('dia').all()
    
    # Ações mais comuns
    acoes_comuns = db.session.query(
        AuditLog.action,
        db.func.count(AuditLog.id).label('total')
    ).filter(
        AuditLog.timestamp >= data_inicio
    ).group_by(AuditLog.action).order_by(desc('total')).limit(10).all()
    
    # Usuários mais ativos
    usuarios_ativos = db.session.query(
        AuditLog.user_name,
        db.func.count(AuditLog.id).label('total')
    ).filter(
        and_(
            AuditLog.timestamp >= data_inicio,
            AuditLog.user_name.isnot(None)
        )
    ).group_by(AuditLog.user_name).order_by(desc('total')).limit(10).all()
    
    # Erros
    total_erros = query_tenant(AuditLog).filter(
        and_(
            AuditLog.timestamp >= data_inicio,
            AuditLog.status.in_(['FAILED', 'ERROR'])
        )
    ).count()
    
    return jsonify({
        'periodo_dias': dias,
        'total_logs': total_logs,
        'total_erros': total_erros,
        'logs_por_dia': [{'dia': str(dia), 'total': total} for dia, total in logs_por_dia],
        'acoes_comuns': [{'action': action, 'total': total} for action, total in acoes_comuns],
        'usuarios_ativos': [{'user': user, 'total': total} for user, total in usuarios_ativos]
    })


# =============================================================================
# ROTAS DE EXPORTAÇÃO
# =============================================================================

@audit_bp.route('/exportar/csv')
@login_required
@role_required('admin')
def exportar_csv():
    """Exporta logs para CSV."""
    
    # Obtém filtros
    action = request.args.get('action', '')
    resource_type = request.args.get('resource_type', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    
    # Query
    query = query_tenant(AuditLog)
    
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)
    if data_inicio:
        try:
            dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp >= dt_inicio)
        except:
            pass
    if data_fim:
        try:
            dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            query = query.filter(AuditLog.timestamp <= dt_fim)
        except:
            pass
    
    logs = query.order_by(desc(AuditLog.timestamp)).limit(10000).all()  # Limite de 10k registros
    
    # Cria CSV em memória
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho
    writer.writerow([
        'ID', 'Data/Hora', 'Usuário', 'Role', 'Ação', 'Recurso', 'ID Recurso',
        'Status', 'IP', 'Motivo', 'Erro', 'Severidade'
    ])
    
    # Dados
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
            log.user_name or '',
            log.user_role or '',
            log.action or '',
            log.resource_type or '',
            log.resource_id or '',
            log.status or '',
            log.ip_address or '',
            log.reason or '',
            log.error_message or '',
            log.severity or ''
        ])
    
    # Prepara arquivo para download
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM para Excel
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'audit_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


@audit_bp.route('/exportar/viagens-csv')
@login_required
@role_required('admin')
def exportar_viagens_csv():
    """Exporta logs de viagens para CSV."""
    
    viagem_id = request.args.get('viagem_id', type=int)
    motorista_id = request.args.get('motorista_id', type=int)
    
    query = query_tenant(ViagemAuditoria)
    
    if viagem_id:
        query = query.filter_by(viagem_id=viagem_id)
    if motorista_id:
        query = query.filter_by(motorista_id=motorista_id)
    
    logs = query.order_by(desc(ViagemAuditoria.timestamp)).limit(10000).all()
    
    # Cria CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'ID', 'Data/Hora', 'Viagem ID', 'Motorista', 'Ação',
        'Status Anterior', 'Status Novo', 'Motivo', 'Valor Repasse', 'IP'
    ])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
            log.viagem_id or '',
            log.motorista_nome or '',
            log.action or '',
            log.status_anterior or '',
            log.status_novo or '',
            log.reason or '',
            log.valor_repasse_novo or '',
            log.ip_address or ''
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'viagens_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


# =============================================================================
# FIM DAS ROTAS DE AUDITORIA
# =============================================================================

