"""
Decorators Multi-Tenant
=======================

Decorators para validar acesso por empresa em rotas protegidas.

Uso:
    from app.decorators_tenant import empresa_required, acesso_empresa_required
    
    @app.route('/viagens')
    @login_required
    @empresa_required
    def listar_viagens():
        # Código aqui só executa se houver empresa ativa
        pass
"""

import logging
from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify
from flask_login import current_user

logger = logging.getLogger(__name__)


def empresa_required(f):
    """
    Decorator que garante que há uma empresa ativa na sessão.
    
    Redireciona para login se não houver empresa definida.
    
    Uso:
        @app.route('/dashboard')
        @login_required
        @empresa_required
        def dashboard():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('empresa_ativa_slug'):
            logger.warning(f"Acesso negado: sem empresa ativa - User: {current_user.email if current_user.is_authenticated else 'anônimo'}")
            
            # Se for requisição AJAX, retornar JSON
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Sessão expirada. Faça login novamente.',
                    'redirect': url_for('auth.login')
                }), 401
            
            flash('Selecione uma empresa para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def acesso_empresa_required(f):
    """
    Decorator que valida se usuário tem acesso à empresa ativa.
    
    Verifica:
    1. Se há empresa ativa na sessão
    2. Se o usuário tem permissão para acessar essa empresa
    
    Admin e Operador têm acesso a todas as empresas.
    
    Uso:
        @app.route('/relatorios')
        @login_required
        @acesso_empresa_required
        def relatorios():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        empresa_slug = session.get('empresa_ativa_slug')
        
        # Verificar se há empresa ativa
        if not empresa_slug:
            logger.warning(f"Acesso negado: sem empresa ativa - User: {current_user.email}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Sessão expirada. Faça login novamente.',
                    'redirect': url_for('auth.login')
                }), 401
            
            flash('Selecione uma empresa para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Admin e Operador têm acesso a todas
        if current_user.role in ['admin', 'operador']:
            return f(*args, **kwargs)
        
        # Verificar acesso do usuário à empresa
        if not current_user.tem_acesso_empresa(empresa_slug):
            logger.warning(f"Acesso negado: {current_user.email} não tem acesso à empresa {empresa_slug}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Você não tem acesso a esta empresa.'
                }), 403
            
            flash('Você não tem acesso a esta empresa.', 'danger')
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    return decorated_function


def motorista_multi_empresa(f):
    """
    Decorator específico para motoristas com acesso a múltiplas empresas.
    
    Valida se o motorista tem acesso à empresa ativa.
    Para outros perfis, apenas passa adiante.
    
    Uso:
        @app.route('/motorista/viagens')
        @login_required
        @motorista_multi_empresa
        def minhas_viagens():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Se não for motorista, apenas passar adiante
        if current_user.role != 'motorista':
            return f(*args, **kwargs)
        
        empresa_slug = session.get('empresa_ativa_slug')
        
        # Verificar se há empresa ativa
        if not empresa_slug:
            logger.warning(f"Motorista sem empresa ativa: {current_user.email}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Sessão expirada. Faça login novamente.',
                    'redirect': url_for('auth.login')
                }), 401
            
            flash('Selecione uma empresa para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Verificar se motorista tem acesso à empresa
        if current_user.motorista and not current_user.motorista.tem_acesso_empresa(empresa_slug):
            logger.warning(f"Motorista {current_user.email} não tem acesso à empresa {empresa_slug}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Você não tem acesso a esta empresa.'
                }), 403
            
            flash('Você não tem acesso a esta empresa.', 'danger')
            return redirect(url_for('motorista.dashboard_motorista'))
        
        return f(*args, **kwargs)
    return decorated_function


def admin_ou_operador_required(f):
    """
    Decorator que restringe acesso apenas a Admin ou Operador.
    
    Uso:
        @app.route('/admin/configuracoes')
        @login_required
        @admin_ou_operador_required
        def configuracoes():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['admin', 'operador']:
            logger.warning(f"Acesso negado: {current_user.email} ({current_user.role}) tentou acessar área restrita")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Acesso restrito a administradores.'
                }), 403
            
            flash('Acesso restrito a administradores.', 'danger')
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function


def log_acesso_empresa(f):
    """
    Decorator que registra log de acesso a recursos por empresa.
    
    Útil para auditoria de acessos multi-tenant.
    
    Uso:
        @app.route('/financeiro')
        @login_required
        @empresa_required
        @log_acesso_empresa
        def financeiro():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        empresa_slug = session.get('empresa_ativa_slug')
        empresa_nome = session.get('empresa_ativa_nome', empresa_slug)
        
        logger.info(
            f"Acesso: {current_user.email} ({current_user.role}) -> "
            f"{request.endpoint} | Empresa: {empresa_nome} | "
            f"IP: {request.remote_addr}"
        )
        
        return f(*args, **kwargs)
    return decorated_function
