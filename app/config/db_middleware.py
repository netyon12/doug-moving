# app/config/db_middleware.py
"""
Middleware de Roteamento Multi-Tenant

Este módulo implementa o roteamento automático de queries para o banco
da empresa ativa na sessão do usuário.

Funcionamento:
1. Antes de cada request, verifica qual empresa está ativa
2. Se for banco remoto, troca a conexão do SQLAlchemy
3. Após o request, restaura a conexão original

Uso:
    # No __init__.py
    from app.config.db_middleware import init_multitenant_middleware
    init_multitenant_middleware(app)
"""

from flask import session, g, current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import logging

logger = logging.getLogger(__name__)

# Cache de engines por empresa (evita criar conexão a cada request)
_engine_cache = {}


def get_empresa_engine(empresa_slug):
    """
    Obtém ou cria um engine SQLAlchemy para a empresa especificada.
    
    Args:
        empresa_slug: Slug da empresa (ex: 'lear', 'nsg')
        
    Returns:
        Engine SQLAlchemy configurado para o banco da empresa
    """
    global _engine_cache
    
    # Importar aqui para evitar import circular
    from app import db
    from app.models import Empresa
    
    try:
        # PRIORIDADE 1: Se g.empresa_ativa existe (definido pela rota), usar ele
        # Isso resolve o problema de rotas dinâmicas como /consulta-viagens/nsg
        # CRÍTICO: Verificar g.empresa_ativa ANTES do cache!
        if hasattr(g, 'empresa_ativa') and g.empresa_ativa:
            empresa = g.empresa_ativa
            logger.debug(f"Usando g.empresa_ativa: {empresa.nome} (ID: {empresa.id})")
        # PRIORIDADE 2: Senão, verificar cache
        elif empresa_slug in _engine_cache:
            logger.debug(f"Usando engine em cache para: {empresa_slug}")
            return _engine_cache[empresa_slug]
        # PRIORIDADE 3: Senão, buscar no banco padrão (para admin trocando empresa)
        else:
            empresa = Empresa.query.filter_by(slug_licenciado=empresa_slug).first()
            logger.debug(f"Buscando empresa no banco padrão: {empresa_slug}")
        
        if not empresa:
            logger.warning(f"Empresa não encontrada: {empresa_slug}")
            return None
        
        # Se é banco local, usar engine padrão
        if empresa.is_banco_local:
            _engine_cache[empresa_slug] = db.engine
            return db.engine
        
        # Montar URL de conexão para banco remoto
        if not all([empresa.db_host, empresa.db_name, empresa.db_user, empresa.db_pass]):
            logger.warning(f"Configuração incompleta para empresa: {empresa_slug}")
            return None
        
        db_port = empresa.db_port or 5432
        db_url = f"postgresql://{empresa.db_user}:{empresa.db_pass}@{empresa.db_host}:{db_port}/{empresa.db_name}"
        
        # Criar engine com pool de conexões
        engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verifica conexão antes de usar
            pool_recycle=300,    # Recicla conexões a cada 5 minutos
            echo=False
        )
        
        _engine_cache[empresa_slug] = engine
        logger.info(f"Engine criado para empresa: {empresa_slug}")
        
        return engine
        
    except Exception as e:
        logger.error(f"Erro ao criar engine para {empresa_slug}: {str(e)}")
        return None


def get_empresa_session():
    """
    Obtém uma sessão SQLAlchemy para a empresa ativa.
    
    Returns:
        Session SQLAlchemy configurada para o banco da empresa ativa
    """
    empresa_slug = session.get('empresa_ativa_slug')
    is_banco_local = session.get('is_banco_local', True)
    
    # Se é banco local ou não tem empresa definida, usar sessão padrão
    if is_banco_local or not empresa_slug:
        from app import db
        return db.session
    
    # Verificar se já tem sessão no contexto do request
    if hasattr(g, 'empresa_session') and g.empresa_session:
        return g.empresa_session
    
    # Criar sessão para banco remoto
    engine = get_empresa_engine(empresa_slug)
    if not engine:
        from app import db
        return db.session
    
    Session = scoped_session(sessionmaker(bind=engine))
    g.empresa_session = Session()
    
    return g.empresa_session


def init_multitenant_middleware(app):
    """
    Inicializa o middleware multi-tenant na aplicação Flask.
    
    Args:
        app: Instância da aplicação Flask
    """
    
    @app.before_request
    def before_request_multitenant():
        """
        Executado antes de cada request.
        Configura a sessão do banco para a empresa ativa.
        """
        from flask_login import current_user
        
        # Ignorar requests estáticos e de autenticação
        from flask import request
        if request.endpoint and (
            request.endpoint.startswith('static') or
            request.endpoint in ['auth.login', 'auth.logout']
        ):
            return
        
        # Verificar se há empresa ativa na sessão
        empresa_slug = session.get('empresa_ativa_slug')
        is_banco_local = session.get('is_banco_local', True)
        
        # Armazenar informações no contexto do request
        g.empresa_slug = empresa_slug
        g.is_banco_local = is_banco_local
        g.empresa_session = None
        
        # Se é banco remoto, preparar engine
        if not is_banco_local and empresa_slug:
            engine = get_empresa_engine(empresa_slug)
            if engine:
                g.empresa_engine = engine
                logger.debug(f"Request configurado para empresa: {empresa_slug}")
    
    @app.teardown_request
    def teardown_request_multitenant(exception=None):
        """
        Executado após cada request.
        Limpa a sessão do banco remoto se existir.
        """
        empresa_session = getattr(g, 'empresa_session', None)
        if empresa_session:
            try:
                if exception:
                    empresa_session.rollback()
                else:
                    empresa_session.commit()
            except Exception as e:
                logger.error(f"Erro ao finalizar sessão: {str(e)}")
            finally:
                empresa_session.close()
    
    logger.info("[OK] Middleware Multi-Tenant inicializado")


def execute_on_empresa(empresa_slug, callback):
    """
    Executa uma função no contexto de uma empresa específica.
    
    Útil para operações que precisam acessar banco de outra empresa
    sem mudar a empresa ativa da sessão.
    
    Args:
        empresa_slug: Slug da empresa
        callback: Função a ser executada (recebe session como parâmetro)
        
    Returns:
        Resultado da função callback
        
    Example:
        def buscar_motorista(session):
            return session.query(Motorista).filter_by(cpf='123').first()
        
        motorista = execute_on_empresa('nsg', buscar_motorista)
    """
    engine = get_empresa_engine(empresa_slug)
    if not engine:
        raise Exception(f"Não foi possível conectar ao banco da empresa: {empresa_slug}")
    
    Session = sessionmaker(bind=engine)
    session_empresa = Session()
    
    try:
        result = callback(session_empresa)
        session_empresa.commit()
        return result
    except Exception as e:
        session_empresa.rollback()
        raise e
    finally:
        session_empresa.close()


# Função helper para usar nos blueprints
def get_db():
    """
    Obtém a sessão do banco para a empresa ativa.
    
    Use esta função em vez de db.session para queries multi-tenant.
    
    Returns:
        Session SQLAlchemy da empresa ativa
        
    Example:
        from app.config.db_middleware import get_db
        
        db_session = get_db()
        viagens = db_session.query(Viagem).filter_by(status='Pendente').all()
    """
    return get_empresa_session()
