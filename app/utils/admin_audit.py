# -*- coding: utf-8 -*-
"""
Módulo de Auditoria e Logs - Sistema Go Mobi
=============================================

Sistema centralizado de auditoria seguindo melhores práticas:
- GDPR (Europa)
- SOX (Sarbanes-Oxley)
- ISO 27001
- LGPD (Brasil)

Funcionalidades:
- Registro automático de todas as operações
- Rastreabilidade completa de ações
- Logs imutáveis e seguros
- Análise e relatórios
- Decorators para automatizar logging

Autor: Sistema DOUG Moving
Data: Outubro 2025
"""

from flask import request, session
from flask_login import current_user
from datetime import datetime
from functools import wraps
import json
import time

from .. import db
from ..models import AuditLog, ViagemAuditoria


# ===========================================================================================
# CONSTANTES - TIPOS DE AÇÕES
# ===========================================================================================

class AuditAction:
    """Constantes para tipos de ações auditadas."""

    # Autenticação
    LOGIN_SUCCESS = 'LOGIN_SUCCESS'
    LOGIN_FAILED = 'LOGIN_FAILED'
    LOGOUT = 'LOGOUT'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET = 'PASSWORD_RESET'

    # CRUD Geral
    CREATE = 'CREATE'
    READ = 'READ'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    BULK_DELETE = 'BULK_DELETE'

    # Viagens
    VIAGEM_CRIADA = 'VIAGEM_CRIADA'
    VIAGEM_ACEITA = 'VIAGEM_ACEITA'
    VIAGEM_INICIADA = 'VIAGEM_INICIADA'
    VIAGEM_FINALIZADA = 'VIAGEM_FINALIZADA'
    VIAGEM_CANCELADA = 'VIAGEM_CANCELADA'
    MOTORISTA_DESASSOCIADO = 'MOTORISTA_DESASSOCIADO'
    STATUS_ALTERADO = 'STATUS_ALTERADO'

    # Administração
    USER_CREATED = 'USER_CREATED'
    USER_UPDATED = 'USER_UPDATED'
    USER_DELETED = 'USER_DELETED'
    ROLE_ASSIGNED = 'ROLE_ASSIGNED'
    PERMISSION_CHANGED = 'PERMISSION_CHANGED'
    CONFIG_UPDATED = 'CONFIG_UPDATED'


class AuditSeverity:
    """Níveis de severidade dos logs."""
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


# ===========================================================================================
# FUNÇÕES PRINCIPAIS DE AUDITORIA
# ===========================================================================================

def log_audit(
    action,
    resource_type,
    resource_id=None,
    status='SUCCESS',
    changes=None,
    reason=None,
    error_message=None,
    severity='INFO',
    user_id=None,
    user_name=None,
    user_role=None,
    duration_ms=None
):
    """
    Registra uma ação no log de auditoria geral.

    Args:
        action (str): Tipo de ação (use constantes de AuditAction)
        resource_type (str): Tipo de recurso afetado (Viagem, User, Motorista, etc.)
        resource_id (int, optional): ID do recurso afetado
        status (str): Status da operação (SUCCESS, FAILED, ERROR)
        changes (dict, optional): Dicionário com mudanças (before/after)
        reason (str, optional): Motivo da ação
        error_message (str, optional): Mensagem de erro se falhou
        severity (str): Nível de severidade (INFO, WARNING, ERROR, CRITICAL)
        user_id (int, optional): ID do usuário (pega do current_user se não fornecido)
        user_name (str, optional): Nome do usuário
        user_role (str, optional): Role do usuário
        duration_ms (int, optional): Tempo de execução em milissegundos

    Returns:
        AuditLog: Objeto do log criado
    """
    try:
        # Obtém informações do usuário atual se não fornecidas
        if user_id is None and current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_name = user_name or current_user.email
            user_role = user_role or current_user.role

        # Obtém informações da requisição
        ip_address = None
        user_agent = None
        request_method = None
        route = None
        session_id = None

        if request:
            ip_address = request.remote_addr
            user_agent = request.headers.get(
                'User-Agent', '')[:255]  # Limita a 255 chars
            request_method = request.method
            route = request.path
            session_id = session.get('_id', None)

        # Converte changes para JSON se for dict
        changes_json = None
        if changes:
            try:
                changes_json = json.dumps(
                    changes, ensure_ascii=False, default=str)
            except Exception as e:
                changes_json = str(changes)

        # Cria o registro de auditoria
        audit_log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_name=user_name,
            user_role=user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            route=route,
            module=request.blueprint if request else None,
            changes=changes_json,
            reason=reason,
            # Limita a 100 caracteres
            error_message=error_message[:100] if error_message else None,
            session_id=session_id,
            duration_ms=duration_ms,
            severity=severity
        )

        db.session.add(audit_log)
        db.session.commit()

        return audit_log

    except Exception as e:
        # Em caso de erro ao criar log, não deve quebrar a aplicação
        # Apenas imprime o erro (em produção, usar logging adequado)
        print(f"ERRO ao criar audit log: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return None


def log_viagem_audit(
    viagem_id,
    action,
    motorista_id=None,
    motorista_nome=None,
    status_anterior=None,
    status_novo=None,
    changes=None,
    reason=None,
    valor_repasse_anterior=None,
    valor_repasse_novo=None,
    user_id=None,
    user_name=None,
    user_role=None
):
    """
    Registra uma ação específica de viagem no log de auditoria de viagens.

    Args:
        viagem_id (int): ID da viagem
        action (str): Tipo de ação (use constantes de AuditAction)
        motorista_id (int, optional): ID do motorista envolvido
        motorista_nome (str, optional): Nome do motorista
        status_anterior (str, optional): Status antes da mudança
        status_novo (str, optional): Status após a mudança
        changes (dict, optional): Dicionário com mudanças detalhadas
        reason (str, optional): Motivo da ação (importante para cancelamentos)
        valor_repasse_anterior (float, optional): Valor de repasse anterior
        valor_repasse_novo (float, optional): Valor de repasse novo
        user_id (int, optional): ID do usuário
        user_name (str, optional): Nome do usuário
        user_role (str, optional): Role do usuário

    Returns:
        ViagemAuditoria: Objeto do log criado
    """
    try:
        # Obtém informações do usuário atual se não fornecidas
        if user_id is None and current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_name = user_name or current_user.email
            user_role = user_role or current_user.role

        # Obtém IP da requisição
        ip_address = request.remote_addr if request else None

        # Converte changes para JSON se for dict
        changes_json = None
        if changes:
            try:
                changes_json = json.dumps(
                    changes, ensure_ascii=False, default=str)
            except Exception as e:
                changes_json = str(changes)

        # Cria o registro de auditoria de viagem
        viagem_audit = ViagemAuditoria(
            timestamp=datetime.utcnow(),
            viagem_id=viagem_id,
            user_id=user_id,
            user_name=user_name,
            user_role=user_role,
            motorista_id=motorista_id,
            motorista_nome=motorista_nome,
            action=action,
            status_anterior=status_anterior,
            status_novo=status_novo,
            changes=changes_json,
            reason=reason,
            valor_repasse_anterior=valor_repasse_anterior,
            valor_repasse_novo=valor_repasse_novo,
            ip_address=ip_address
        )

        db.session.add(viagem_audit)
        db.session.commit()

        # Também registra no log geral
        log_audit(
            action=action,
            resource_type='Viagem',
            resource_id=viagem_id,
            status='SUCCESS',
            changes=changes,
            reason=reason,
            severity='INFO',
            user_id=user_id,
            user_name=user_name,
            user_role=user_role
        )

        return viagem_audit

    except Exception as e:
        print(f"ERRO ao criar viagem audit log: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return None


# ===========================================================================================
# DECORATORS PARA AUDITORIA AUTOMÁTICA
# ===========================================================================================

def audit_action(action, resource_type, get_resource_id=None, severity='INFO'):
    """
    Decorator para auditar automaticamente uma função/rota.

    Args:
        action (str): Tipo de ação
        resource_type (str): Tipo de recurso
        get_resource_id (callable, optional): Função para extrair resource_id dos args
        severity (str): Nível de severidade

    Exemplo:
        @audit_action('CREATE', 'Viagem')
        def criar_viagem():
            ...

        @audit_action('UPDATE', 'User', get_resource_id=lambda *args, **kwargs: kwargs.get('user_id'))
        def atualizar_usuario(user_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            error_message = None
            status = 'SUCCESS'

            try:
                # Executa a função
                result = f(*args, **kwargs)

                # Calcula duração
                duration_ms = int((time.time() - start_time) * 1000)

                # Extrai resource_id se função foi fornecida
                resource_id = None
                if get_resource_id:
                    try:
                        resource_id = get_resource_id(*args, **kwargs)
                    except:
                        pass

                # Registra no log
                log_audit(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    status=status,
                    severity=severity,
                    duration_ms=duration_ms
                )

                return result

            except Exception as e:
                # Em caso de erro
                status = 'ERROR'
                error_message = str(e)
                duration_ms = int((time.time() - start_time) * 1000)

                # Registra erro no log
                log_audit(
                    action=action,
                    resource_type=resource_type,
                    status=status,
                    error_message=error_message,
                    severity='ERROR',
                    duration_ms=duration_ms
                )

                # Re-lança a exceção
                raise

        return decorated_function
    return decorator


# ===========================================================================================
# FUNÇÕES AUXILIARES
# ===========================================================================================

def get_changes_dict(old_obj, new_obj, fields):
    """
    Compara dois objetos e retorna um dicionário com as mudanças.

    Args:
        old_obj: Objeto antigo (ou dict)
        new_obj: Objeto novo (ou dict)
        fields (list): Lista de campos para comparar

    Returns:
        dict: Dicionário com before/after para campos que mudaram
    """
    changes = {}

    for field in fields:
        # Obtém valores (suporta objetos e dicts)
        old_value = getattr(old_obj, field, None) if hasattr(
            old_obj, field) else old_obj.get(field)
        new_value = getattr(new_obj, field, None) if hasattr(
            new_obj, field) else new_obj.get(field)

        # Compara valores
        if old_value != new_value:
            changes[field] = {
                'before': str(old_value) if old_value is not None else None,
                'after': str(new_value) if new_value is not None else None
            }

    return changes if changes else None


def log_login_attempt(username, success, reason=None):
    """
    Registra tentativa de login.

    Args:
        username (str): Nome de usuário
        success (bool): Se login foi bem-sucedido
        reason (str, optional): Motivo da falha
    """
    action = AuditAction.LOGIN_SUCCESS if success else AuditAction.LOGIN_FAILED
    status = 'SUCCESS' if success else 'FAILED'
    severity = 'INFO' if success else 'WARNING'

    log_audit(
        action=action,
        resource_type='User',
        status=status,
        reason=reason,
        severity=severity,
        user_name=username
    )


def log_logout(user_id, username):
    """
    Registra logout de usuário.

    Args:
        user_id (int): ID do usuário
        username (str): Nome do usuário
    """
    log_audit(
        action=AuditAction.LOGOUT,
        resource_type='User',
        resource_id=user_id,
        status='SUCCESS',
        severity='INFO',
        user_id=user_id,
        user_name=username
    )


# ===========================================================================================
# FUNÇÕES DE CONSULTA E ANÁLISE
# ===========================================================================================

def get_user_activity(user_id, limit=100):
    """
    Retorna atividades recentes de um usuário.

    Args:
        user_id (int): ID do usuário
        limit (int): Número máximo de registros

    Returns:
        list: Lista de AuditLog
    """
    return AuditLog.query.filter_by(user_id=user_id)\
        .order_by(AuditLog.timestamp.desc())\
        .limit(limit)\
        .all()


def get_viagem_history(viagem_id):
    """
    Retorna histórico completo de uma viagem.

    Args:
        viagem_id (int): ID da viagem

    Returns:
        list: Lista de ViagemAuditoria ordenada cronologicamente
    """
    return ViagemAuditoria.query.filter_by(viagem_id=viagem_id)\
        .order_by(ViagemAuditoria.timestamp.asc())\
        .all()


def get_recent_logs(limit=100, severity=None, action=None, resource_type=None):
    """
    Retorna logs recentes com filtros opcionais.

    Args:
        limit (int): Número máximo de registros
        severity (str, optional): Filtrar por severidade
        action (str, optional): Filtrar por ação
        resource_type (str, optional): Filtrar por tipo de recurso

    Returns:
        list: Lista de AuditLog
    """
    query = AuditLog.query

    if severity:
        query = query.filter_by(severity=severity)
    if action:
        query = query.filter_by(action=action)
    if resource_type:
        query = query.filter_by(resource_type=resource_type)

    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def get_failed_operations(limit=50):
    """
    Retorna operações que falharam recentemente.

    Args:
        limit (int): Número máximo de registros

    Returns:
        list: Lista de AuditLog com status FAILED ou ERROR
    """
    return AuditLog.query.filter(
        AuditLog.status.in_(['FAILED', 'ERROR'])
    ).order_by(AuditLog.timestamp.desc()).limit(limit).all()


# ===========================================================================================
# FIM DO MÓDULO DE AUDITORIA
# ===========================================================================================
