"""
Helper de Conexão Multi-Banco
=============================

Funções auxiliares para obter sessão do banco correto
baseado na empresa ativa na sessão do usuário.

Uso:
    from app.config.db_helper import get_db_empresa, set_empresa_ativa
    
    # Definir empresa ativa (após login)
    set_empresa_ativa(empresa)
    
    # Obter sessão do banco da empresa ativa
    db = get_db_empresa()
    viagens = db.query(Viagem).all()
"""

import logging
from flask import session, g
from flask_login import current_user

logger = logging.getLogger(__name__)


def get_db_referencia():
    """
    Retorna sessão do Banco de Referência (Banco 1).
    
    Usado para:
    - Autenticação inicial
    - Busca de empresas
    - Operações que sempre devem ir ao banco principal
    
    Returns:
        Sessão SQLAlchemy do banco de referência
    """
    from app import db
    return db.session


def get_db_empresa():
    """
    Retorna sessão do banco da empresa ativa na sessão do usuário.
    
    Usa a empresa armazenada na sessão Flask para determinar
    qual banco de dados deve ser consultado.
    
    Returns:
        Sessão SQLAlchemy do banco da empresa ativa
        
    Raises:
        Exception: Se nenhuma empresa ativa na sessão
    """
    empresa_slug = session.get('empresa_ativa_slug')
    
    if not empresa_slug:
        logger.warning("Tentativa de acessar banco sem empresa ativa na sessão")
        raise Exception('Nenhuma empresa ativa na sessão. Faça login novamente.')
    
    # Se for banco local (GOMOBI, LEAR), usar sessão padrão do Flask
    is_banco_local = session.get('is_banco_local', True)
    
    if is_banco_local:
        from app import db
        return db.session
    
    # Banco remoto: usar db_manager
    from app.config.database_config import db_manager
    return db_manager.get_session(empresa_slug)


def get_empresa_ativa():
    """
    Retorna objeto Empresa ativa na sessão.
    
    Returns:
        Objeto Empresa ou None se não houver empresa ativa
    """
    from app.models import Empresa
    
    empresa_slug = session.get('empresa_ativa_slug')
    
    if not empresa_slug:
        return None
    
    return Empresa.query.filter_by(slug_licenciado=empresa_slug).first()


def get_empresa_ativa_id():
    """
    Retorna ID da empresa ativa na sessão.
    
    Returns:
        int: ID da empresa ou None
    """
    return session.get('empresa_ativa_id')


def get_empresa_ativa_slug():
    """
    Retorna slug da empresa ativa na sessão.
    
    Returns:
        str: Slug da empresa (ex: 'lear', 'nsg') ou None
    """
    return session.get('empresa_ativa_slug')


def is_banco_local():
    """
    Verifica se a empresa ativa usa banco local.
    
    Returns:
        bool: True se banco local, False se remoto
    """
    return session.get('is_banco_local', True)


def set_empresa_ativa(empresa):
    """
    Define empresa ativa na sessão do usuário.
    
    Armazena informações necessárias para roteamento de banco
    na sessão Flask.
    
    Args:
        empresa: Objeto Empresa a definir como ativa
    """
    session['empresa_ativa_id'] = empresa.id
    session['empresa_ativa_slug'] = empresa.slug_licenciado
    session['empresa_ativa_nome'] = empresa.nome
    session['is_banco_local'] = empresa.is_banco_local
    
    logger.info(f"Empresa ativa definida: {empresa.nome} (slug={empresa.slug_licenciado}, local={empresa.is_banco_local})")


def limpar_empresa_ativa():
    """
    Remove empresa ativa da sessão (usado no logout).
    """
    session.pop('empresa_ativa_id', None)
    session.pop('empresa_ativa_slug', None)
    session.pop('empresa_ativa_nome', None)
    session.pop('is_banco_local', None)
    
    logger.info("Empresa ativa removida da sessão")


def buscar_motorista_por_cpf(cpf, empresa_slug=None):
    """
    Busca motorista por CPF no banco da empresa.
    
    Usado para localizar o motorista correto quando ele troca
    de empresa, já que os IDs são diferentes em cada banco.
    
    Args:
        cpf: CPF do motorista (com ou sem formatação)
        empresa_slug: Slug da empresa (opcional, usa empresa ativa se não informado)
    
    Returns:
        Objeto Motorista ou None se não encontrado
    """
    from app.models import Motorista
    
    # Normalizar CPF (remover formatação)
    cpf_limpo = ''.join(filter(str.isdigit, cpf)) if cpf else None
    
    if not cpf_limpo:
        return None
    
    if empresa_slug:
        # Buscar em banco específico
        from app.config.database_config import db_manager
        
        try:
            empresa = db_manager._get_empresa_by_slug(empresa_slug)
            if not empresa:
                return None
            
            if empresa.is_banco_local:
                # Banco local
                return Motorista.query.filter(
                    Motorista.cpf_cnpj.like(f'%{cpf_limpo}%')
                ).first()
            else:
                # Banco remoto
                db_session = db_manager.get_session(empresa_slug)
                return db_session.query(Motorista).filter(
                    Motorista.cpf_cnpj.like(f'%{cpf_limpo}%')
                ).first()
        except Exception as e:
            logger.error(f"Erro ao buscar motorista por CPF: {e}")
            return None
    else:
        # Usar banco da empresa ativa
        db = get_db_empresa()
        return db.query(Motorista).filter(
            Motorista.cpf_cnpj.like(f'%{cpf_limpo}%')
        ).first()


def get_empresas_disponiveis_usuario():
    """
    Retorna lista de empresas disponíveis para o usuário atual.
    
    - Admin/Operador: Todas as empresas ativas
    - Motorista: Empresas no campo empresas_acesso
    - Gerente/Supervisor: Empresa específica
    
    Returns:
        list: Lista de objetos Empresa
    """
    from app.models import Empresa
    
    if not current_user.is_authenticated:
        return []
    
    # Admin e Operador: todas as empresas ativas
    if current_user.role in ['admin', 'operador']:
        return Empresa.query.filter_by(status='Ativo').order_by(Empresa.nome).all()
    
    # Motorista: empresas do campo empresas_acesso
    if current_user.role == 'motorista' and current_user.motorista:
        slugs = current_user.motorista.get_empresas_lista()
        if slugs:
            return Empresa.query.filter(
                Empresa.slug_licenciado.in_(slugs),
                Empresa.status == 'Ativo'
            ).order_by(Empresa.nome).all()
        return []
    
    # Gerente/Supervisor: empresas do campo empresas_acesso do User
    slugs = current_user.get_empresas_lista()
    if slugs:
        return Empresa.query.filter(
            Empresa.slug_licenciado.in_(slugs),
            Empresa.status == 'Ativo'
        ).order_by(Empresa.nome).all()
    
    return []


def pode_trocar_empresa():
    """
    Verifica se o usuário atual pode trocar de empresa.
    
    Returns:
        bool: True se pode trocar (Admin, Operador, ou Motorista multi-empresa)
    """
    if not current_user.is_authenticated:
        return False
    
    # Admin e Operador sempre podem trocar
    if current_user.role in ['admin', 'operador']:
        return True
    
    # Motorista: verificar se tem acesso a mais de uma empresa
    if current_user.role == 'motorista' and current_user.motorista:
        return len(current_user.motorista.get_empresas_lista()) > 1
    
    return False
