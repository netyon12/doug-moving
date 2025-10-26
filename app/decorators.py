# Em app/decorators.py

from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user


def permission_required(permission):
    """
    Decorator que verifica se o usuário logado tem a permissão necessária.
    A 'permissão' é simplesmente o nome do 'role' (ex: 'admin', 'gerente').
    Pode ser uma string única ou uma lista de strings.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Converte a permissão para uma lista, caso seja uma string única
            if isinstance(permission, str):
                permissions = [permission]
            else:
                permissions = permission

            # Se o perfil do usuário não estiver na lista de permissões, bloqueia o acesso.
            if current_user.role not in permissions:
                # Você pode personalizar a ação de bloqueio aqui.
                # Opção 1: Mostrar uma página de "Acesso Negado" (403 Forbidden)
                abort(403)

                # Opção 2: Redirecionar para a home com uma mensagem
                # flash('Você não tem permissão para acessar esta página.', 'danger')
                # return redirect(url_for('home'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(role):
    """
    Decorator que verifica se o usuário logado tem o role necessário.
    É um alias para permission_required, mantendo compatibilidade.

    Args:
        role: String com o nome do role (ex: 'admin', 'motorista', 'supervisor')
              ou lista de roles permitidos

    Uso:
        @role_required('motorista')
        def minha_rota():
            ...
    """
    return permission_required(role)


def agrupamento_required(f):
    """
    Decorator que permite acesso ao agrupamento apenas para Admin e Gerente.
    Supervisor NÃO tem acesso.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Você precisa estar autenticado para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))

        # Apenas Admin e Gerente podem acessar agrupamento
        if current_user.role not in ['admin', 'gerente']:
            flash(
                'Acesso negado. Apenas Administradores e Gerentes podem acessar o Agrupamento.', 'error')
            abort(403)

        return f(*args, **kwargs)
    return decorated_function
