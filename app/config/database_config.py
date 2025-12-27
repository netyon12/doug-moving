"""
Configuração Multi-Tenant de Banco de Dados
============================================

Gerencia conexões com múltiplos bancos de dados para arquitetura multi-tenant.

Estrutura:
- Banco 1 (GOMOBI/LEAR): Banco de referência (DATABASE_URL do .env)
- Banco 2+ (NSG, etc.): Bancos remotos configurados na tabela 'empresa'

Uso:
    from app.config.database_config import db_manager
    
    # Obter sessão para empresa específica
    session = db_manager.get_session('nsg')
    
    # Obter engine para empresa
    engine = db_manager.get_engine('nsg')
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gerenciador de conexões multi-banco.
    
    Mantém um pool de conexões para cada banco de dados configurado,
    permitindo acesso isolado aos dados de cada empresa.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de conexões."""
        self._engines = {}
        self._sessions = {}
        self._banco_referencia_url = None
        self._empresas_cache = {}
    
    @property
    def banco_referencia_url(self):
        """Retorna URL do banco de referência (lazy loading)."""
        if self._banco_referencia_url is None:
            self._banco_referencia_url = os.getenv('DATABASE_URL')
        return self._banco_referencia_url
    
    def _get_empresa_by_slug(self, slug):
        """
        Busca empresa no banco de referência pelo slug.
        
        Args:
            slug: Slug do licenciado (ex: 'lear', 'nsg')
            
        Returns:
            Objeto Empresa ou None
        """
        # Cache para evitar consultas repetidas
        if slug in self._empresas_cache:
            return self._empresas_cache[slug]
        
        # Importar aqui para evitar circular import
        from app.models import Empresa
        
        empresa = Empresa.query.filter_by(
            slug_licenciado=slug.lower(),
            status='Ativo'
        ).first()
        
        if empresa:
            self._empresas_cache[slug] = empresa
        
        return empresa
    
    def _build_db_url(self, empresa):
        """
        Constrói URL de conexão para banco da empresa.
        
        Args:
            empresa: Objeto Empresa
            
        Returns:
            str: URL de conexão PostgreSQL
        """
        if empresa.is_banco_local:
            return self.banco_referencia_url
        
        # Construir URL para banco remoto
        # Formato: postgresql://user:pass@host:port/dbname
        return (
            f"postgresql://{empresa.db_user}:{empresa.db_pass}"
            f"@{empresa.db_host}:{empresa.db_port}/{empresa.db_name}"
        )
    
    def get_engine(self, empresa_or_slug):
        """
        Retorna engine SQLAlchemy para banco da empresa.
        
        Args:
            empresa_or_slug: Objeto Empresa ou slug string
            
        Returns:
            Engine SQLAlchemy
            
        Raises:
            ValueError: Se empresa não encontrada
        """
        # Resolver empresa se for string
        if isinstance(empresa_or_slug, str):
            empresa = self._get_empresa_by_slug(empresa_or_slug)
            if not empresa:
                raise ValueError(f"Empresa '{empresa_or_slug}' não encontrada ou inativa")
        else:
            empresa = empresa_or_slug
        
        # Se for banco local, usar URL padrão
        if empresa.is_banco_local:
            cache_key = 'local'
        else:
            cache_key = f"remote_{empresa.id}"
        
        # Criar engine se não existir no cache
        if cache_key not in self._engines:
            db_url = self._build_db_url(empresa)
            
            logger.info(f"Criando engine para empresa: {empresa.nome} (is_local={empresa.is_banco_local})")
            
            self._engines[cache_key] = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,  # Reciclar conexões a cada 30 min
                echo=False
            )
        
        return self._engines[cache_key]
    
    def get_session(self, empresa_or_slug):
        """
        Retorna sessão SQLAlchemy para banco da empresa.
        
        Args:
            empresa_or_slug: Objeto Empresa ou slug string
            
        Returns:
            Sessão SQLAlchemy
            
        Raises:
            ValueError: Se empresa não encontrada
        """
        # Resolver empresa se for string
        if isinstance(empresa_or_slug, str):
            empresa = self._get_empresa_by_slug(empresa_or_slug)
            if not empresa:
                raise ValueError(f"Empresa '{empresa_or_slug}' não encontrada ou inativa")
        else:
            empresa = empresa_or_slug
        
        # Determinar chave de cache
        if empresa.is_banco_local:
            cache_key = 'local'
        else:
            cache_key = f"remote_{empresa.id}"
        
        # Criar session factory se não existir
        if cache_key not in self._sessions:
            engine = self.get_engine(empresa)
            session_factory = sessionmaker(bind=engine)
            self._sessions[cache_key] = scoped_session(session_factory)
        
        return self._sessions[cache_key]()
    
    def get_session_local(self):
        """
        Retorna sessão do banco local (referência).
        
        Útil para consultas que sempre devem ir ao banco principal,
        como busca de empresas e autenticação inicial.
        
        Returns:
            Sessão SQLAlchemy do banco local
        """
        if 'local' not in self._sessions:
            engine = create_engine(
                self.banco_referencia_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800,
                echo=False
            )
            self._engines['local'] = engine
            session_factory = sessionmaker(bind=engine)
            self._sessions['local'] = scoped_session(session_factory)
        
        return self._sessions['local']()
    
    def clear_cache(self):
        """Limpa cache de empresas (útil após alterações)."""
        self._empresas_cache.clear()
        logger.info("Cache de empresas limpo")
    
    def close_session(self, empresa_or_slug):
        """
        Fecha sessão específica de uma empresa.
        
        Args:
            empresa_or_slug: Objeto Empresa ou slug string
        """
        if isinstance(empresa_or_slug, str):
            empresa = self._get_empresa_by_slug(empresa_or_slug)
            if not empresa:
                return
        else:
            empresa = empresa_or_slug
        
        cache_key = 'local' if empresa.is_banco_local else f"remote_{empresa.id}"
        
        if cache_key in self._sessions:
            self._sessions[cache_key].remove()
            logger.info(f"Sessão fechada para empresa: {empresa.nome}")
    
    def close_all(self):
        """Fecha todas as conexões e sessões."""
        for key, session in self._sessions.items():
            try:
                session.remove()
            except Exception as e:
                logger.error(f"Erro ao fechar sessão {key}: {e}")
        
        for key, engine in self._engines.items():
            try:
                engine.dispose()
            except Exception as e:
                logger.error(f"Erro ao fechar engine {key}: {e}")
        
        self._sessions.clear()
        self._engines.clear()
        self._empresas_cache.clear()
        
        logger.info("Todas as conexões foram fechadas")
    
    def test_connection(self, empresa_or_slug):
        """
        Testa conexão com banco da empresa.
        
        Args:
            empresa_or_slug: Objeto Empresa ou slug string
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            session = self.get_session(empresa_or_slug)
            session.execute("SELECT 1")
            session.close()
            return {'success': True, 'message': 'Conexão OK'}
        except Exception as e:
            logger.error(f"Erro ao testar conexão: {e}")
            return {'success': False, 'message': str(e)}


# Instância global do gerenciador
db_manager = DatabaseManager()
