# app/config/tenant_utils.py
"""
Utilitários Multi-Tenant para uso nos Blueprints

Este módulo fornece funções helper para facilitar o acesso
ao banco da empresa ativa em qualquer parte do código.

Uso nos blueprints:
    from app.config.tenant_utils import get_tenant_session, query_tenant
    
    # Opção 1: Obter sessão e fazer query manual
    session = get_tenant_session()
    viagens = session.query(Viagem).filter_by(status='Pendente').all()
    
    # Opção 2: Query direta com modelo
    viagens = query_tenant(Viagem).filter_by(status='Pendente').all()
"""

from flask import session, g
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def get_tenant_session():
    """
    Obtém a sessão do banco para a empresa ativa.
    
    Se a empresa ativa usa banco local, retorna db.session.
    Se usa banco remoto, retorna uma sessão conectada ao banco remoto.
    
    Returns:
        SQLAlchemy Session
    """
    from app.config.db_middleware import get_empresa_session
    return get_empresa_session()


def query_tenant(model):
    """
    Inicia uma query no banco da empresa ativa.
    
    Args:
        model: Classe do modelo SQLAlchemy (ex: Viagem, Solicitacao)
        
    Returns:
        Query SQLAlchemy
        
    Example:
        viagens = query_tenant(Viagem).filter_by(status='Pendente').all()
    """
    session = get_tenant_session()
    return session.query(model)


def get_or_404_tenant(model, id_value):
    """
    Busca um registro pelo ID no banco da empresa ativa.
    Retorna 404 se não encontrado.
    
    Args:
        model: Classe do modelo SQLAlchemy
        id_value: Valor do ID a buscar
        
    Returns:
        Instância do modelo ou abort(404)
        
    Example:
        empresa = get_or_404_tenant(Empresa, empresa_id)
    """
    from flask import abort
    
    obj = query_tenant(model).filter_by(id=id_value).first()
    if obj is None:
        abort(404)
    return obj


class TenantPagination:
    """
    Classe de paginação compatível com Flask-SQLAlchemy.
    """
    def __init__(self, query, page, per_page, total, items):
        self.query = query
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items
    
    @property
    def pages(self):
        """Total de páginas"""
        if self.per_page == 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page
    
    @property
    def has_prev(self):
        """Tem página anterior"""
        return self.page > 1
    
    @property
    def has_next(self):
        """Tem próxima página"""
        return self.page < self.pages
    
    @property
    def prev_num(self):
        """Número da página anterior"""
        return self.page - 1 if self.has_prev else None
    
    @property
    def next_num(self):
        """Número da próxima página"""
        return self.page + 1 if self.has_next else None


def paginate_tenant(query, page=1, per_page=20, error_out=True, max_per_page=None):
    """
    Pagina uma query do tenant (compatível com Flask-SQLAlchemy paginate).
    
    Args:
        query: Query do SQLAlchemy
        page: Número da página (começa em 1)
        per_page: Itens por página
        error_out: Se True, retorna 404 quando página não existe
        max_per_page: Máximo de itens por página (opcional)
        
    Returns:
        Objeto TenantPagination compatível com Flask-SQLAlchemy
        
    Example:
        viagens = query_tenant(Viagem).filter_by(status='Pendente')
        paginacao = paginate_tenant(viagens, page=1, per_page=10)
    """
    from flask import abort
    
    # Validar per_page
    if max_per_page is not None:
        per_page = min(per_page, max_per_page)
    
    # Calcular offset
    offset = (page - 1) * per_page
    
    # Buscar total de itens
    total = query.count()
    
    # Buscar itens da página
    items = query.limit(per_page).offset(offset).all()
    
    # Verificar se página existe
    if error_out and page > 1 and not items:
        abort(404)
    
    # Criar objeto Pagination
    return TenantPagination(
        query=query,
        page=page,
        per_page=per_page,
        total=total,
        items=items
    )


def is_banco_remoto():
    """
    Verifica se a empresa ativa usa banco remoto.
    
    Returns:
        bool: True se banco remoto, False se local
    """
    return not session.get('is_banco_local', True)


def get_empresa_ativa():
    """
    Obtém informações da empresa ativa.
    
    Returns:
        dict com informações da empresa ativa
    """
    return {
        'id': session.get('empresa_ativa_id'),
        'nome': session.get('empresa_ativa_nome'),
        'slug': session.get('empresa_ativa_slug'),
        'is_banco_local': session.get('is_banco_local', True)
    }


def with_tenant_session(f):
    """
    Decorator que injeta a sessão do tenant como primeiro argumento.
    
    Example:
        @with_tenant_session
        def listar_viagens(db_session, status='Pendente'):
            return db_session.query(Viagem).filter_by(status=status).all()
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db_session = get_tenant_session()
        return f(db_session, *args, **kwargs)
    return decorated_function


def execute_in_tenant(empresa_slug, callback):
    """
    Executa uma função no contexto de uma empresa específica.
    
    Útil para operações que precisam acessar banco de outra empresa.
    
    Args:
        empresa_slug: Slug da empresa (ex: 'nsg')
        callback: Função que recebe session como parâmetro
        
    Returns:
        Resultado do callback
        
    Example:
        def buscar_motorista_por_cpf(session, cpf):
            return session.query(Motorista).filter_by(cpf_cnpj=cpf).first()
        
        motorista_nsg = execute_in_tenant('nsg', lambda s: buscar_motorista_por_cpf(s, '123.456.789-00'))
    """
    from app.config.db_middleware import execute_on_empresa
    return execute_on_empresa(empresa_slug, callback)


# ============================================================
# FUNÇÕES PARA MIGRAÇÃO GRADUAL
# ============================================================

def tenant_query(model, use_tenant=True):
    """
    Query que pode usar tenant ou banco local.
    
    Útil durante a migração gradual do código.
    
    Args:
        model: Classe do modelo
        use_tenant: Se True, usa banco do tenant. Se False, usa db.session
        
    Returns:
        Query SQLAlchemy
    """
    if use_tenant and is_banco_remoto():
        return query_tenant(model)
    else:
        return model.query


def get_session(use_tenant=True):
    """
    Obtém sessão que pode usar tenant ou banco local.
    
    Args:
        use_tenant: Se True, usa banco do tenant. Se False, usa db.session
        
    Returns:
        SQLAlchemy Session
    """
    if use_tenant and is_banco_remoto():
        return get_tenant_session()
    else:
        from app import db
        return db.session
