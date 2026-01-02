"""
Módulo de Sincronização de Usuários Multi-Banco
================================================

Este módulo resolve o problema de IDs de usuários em arquitetura multi-banco.

Problema:
---------
- Sistema possui 2 bancos separados (Banco 1 - LEAR, Banco 2 - NSG)
- Usuário Admin/Operador pode trocar de empresa (troca de banco)
- current_user.id pode ser do Banco 1, mas sistema está conectado no Banco 2
- Ao gravar created_by_user_id, causa erro de Foreign Key

Solução:
--------
- Usar EMAIL como chave única (igual CPF para motoristas)
- Buscar ID do usuário NO BANCO ATUAL usando o email
- Garantir que created_by_user_id sempre seja válido no banco atual

Exemplo:
--------
# ANTES (ERRADO)
created_by_user_id = current_user.id  # ID do Banco 1

# DEPOIS (CORRETO)
created_by_user_id = get_current_user_id_in_current_db()  # ID do Banco 2
"""

from flask_login import current_user


def get_current_user_id_in_current_db():
    """
    Busca o ID do usuário logado NO BANCO ATUAL.
    
    Problema:
        current_user.id pode ser do Banco 1, mas estamos conectados no Banco 2
        
    Solução:
        Buscar por email (único) no banco atual usando query_tenant
        
    Returns:
        int: ID do usuário no banco atual
        None: Se usuário não autenticado ou não encontrado
        
    Exemplo:
        >>> # Usuário Admin logado (Banco 1: id=1, email='admin@lear.com')
        >>> # Troca para empresa NSG (Banco 2)
        >>> current_user.id  # Retorna 1 (Banco 1) ❌
        >>> get_current_user_id_in_current_db()  # Retorna 5 (Banco 2) ✅
    """
    from app.models import User
    from app.config.tenant_utils import query_tenant
    
    if not current_user.is_authenticated:
        return None
    
    # Busca usuário no banco atual por email (chave única)
    user_in_current_db = query_tenant(User).filter_by(
        email=current_user.email
    ).first()
    
    if not user_in_current_db:
        # Usuário não existe no banco atual
        # Isso pode acontecer se Admin/Operador não foi replicado
        print(f"[WARNING] Usuário {current_user.email} não encontrado no banco atual!")
        return None
    
    return user_in_current_db.id


def sync_user_to_banco(user_email, db_session_origem, db_session_destino):
    """
    Sincroniza um usuário (Admin/Operador) do banco de origem para o banco de destino.
    
    Similar à sincronização de motoristas, mas para usuários administrativos.
    
    Args:
        user_email: Email do usuário a sincronizar
        db_session_origem: SQLAlchemy session do banco de origem
        db_session_destino: SQLAlchemy session do banco de destino
        
    Returns:
        tuple: (success: bool, message: str, user_destino: User ou None)
    """
    from app.models import User
    
    try:
        # 1. Buscar usuário no banco de origem
        user_origem = db_session_origem.query(User).filter_by(email=user_email).first()
        
        if not user_origem:
            return (False, f"Usuário {user_email} não encontrado no banco de origem", None)
        
        # 2. Verificar se já existe no banco de destino
        user_destino = db_session_destino.query(User).filter_by(email=user_email).first()
        
        # 3. Se já existe, atualizar
        if user_destino:
            print(f"[SYNC] Usuário {user_email} já existe no banco de destino. Atualizando...")
            user_destino.password = user_origem.password  # Sincronizar senha
            user_destino.role = user_origem.role
            db_session_destino.commit()
            return (True, f"Usuário {user_email} atualizado no banco de destino", user_destino)
        
        # 4. Se não existe, criar
        else:
            print(f"[SYNC] Criando usuário {user_email} no banco de destino...")
            user_destino = User(
                email=user_origem.email,
                password=user_origem.password,  # Mesma senha hasheada
                role=user_origem.role
            )
            db_session_destino.add(user_destino)
            db_session_destino.commit()
            
            return (True, f"Usuário {user_email} criado no banco de destino", user_destino)
            
    except Exception as e:
        db_session_destino.rollback()
        return (False, f"Erro ao sincronizar usuário: {str(e)}", None)
