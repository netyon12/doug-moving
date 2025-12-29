"""
Módulo de Sincronização de Motoristas Multi-Tenant
===================================================

Este módulo gerencia a replicação de motoristas entre o Banco Principal (Banco 1)
e os bancos remotos de cada empresa (ex: Banco 2 - NSG).

Arquitetura:
-----------
- Motoristas são cadastrados inicialmente no Banco 1 (principal)
- Quando um motorista recebe acesso a uma empresa remota (ex: NSG),
  seus dados são replicados no banco dessa empresa
- CPF é usado como chave única para sincronização entre bancos
- Isso garante integridade referencial nas viagens (foreign keys funcionam)

Fluxo:
------
1. Admin cadastra motorista no Banco 1
2. Admin marca acesso à empresa NSG (empresas_acesso = 'lear,nsg')
3. Sistema replica motorista no Banco 2 (NSG) com mesmo CPF
4. Motorista pode logar e trocar para NSG
5. Ao aceitar viagem NSG, viagem.motorista_id aponta para ID do Banco 2 ✅
"""

from flask import session
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash


def sync_motorista_to_empresa(motorista, empresa_slug, db_session_origem, db_session_destino):
    """
    Sincroniza um motorista do banco de origem para o banco de destino.
    
    Args:
        motorista: Objeto Motorista do banco de origem
        empresa_slug: Slug da empresa de destino (ex: 'nsg')
        db_session_origem: SQLAlchemy session do banco de origem
        db_session_destino: SQLAlchemy session do banco de destino
        
    Returns:
        tuple: (success: bool, message: str, motorista_destino: Motorista ou None)
    """
    from app.models import User, Motorista
    
    try:
        # 1. Verificar se motorista já existe no banco de destino (por CPF)
        motorista_destino = None
        user_destino = None
        
        if motorista.cpf_cnpj:
            motorista_destino = db_session_destino.query(Motorista).filter_by(
                cpf_cnpj=motorista.cpf_cnpj
            ).first()
        
        # 2. Se já existe, atualizar dados
        if motorista_destino:
            print(f"[SYNC] Motorista {motorista.nome} (CPF: {motorista.cpf_cnpj}) já existe no banco de {empresa_slug}. Atualizando...")
            
            # Atualizar dados do motorista
            motorista_destino.nome = motorista.nome
            motorista_destino.email = motorista.email
            motorista_destino.telefone = motorista.telefone
            motorista_destino.endereco = motorista.endereco
            motorista_destino.nro = motorista.nro
            motorista_destino.bairro = motorista.bairro
            motorista_destino.cidade = motorista.cidade
            motorista_destino.uf = motorista.uf
            motorista_destino.chave_pix = motorista.chave_pix
            motorista_destino.status = motorista.status
            motorista_destino.veiculo_nome = motorista.veiculo_nome
            motorista_destino.veiculo_placa = motorista.veiculo_placa
            motorista_destino.veiculo_cor = motorista.veiculo_cor
            motorista_destino.veiculo_ano = motorista.veiculo_ano
            motorista_destino.veiculo_km = motorista.veiculo_km
            motorista_destino.veiculo_obs = motorista.veiculo_obs
            motorista_destino.empresas_acesso = motorista.empresas_acesso
            motorista_destino.empresa_padrao_slug = motorista.empresa_padrao_slug
            
            # Atualizar dados do user associado
            user_destino = motorista_destino.user
            if user_destino:
                user_destino.email = motorista.user.email
                # Manter senha do banco de origem
                user_destino.password = motorista.user.password
            
            db_session_destino.commit()
            
            return (True, f"Motorista atualizado no banco de {empresa_slug}", motorista_destino)
        
        # 3. Se não existe, criar novo
        else:
            print(f"[SYNC] Criando motorista {motorista.nome} (CPF: {motorista.cpf_cnpj}) no banco de {empresa_slug}...")
            
            # 3.1. Criar User no banco de destino
            user_destino = User(
                email=motorista.user.email,
                password=motorista.user.password,  # Mesma senha hasheada
                role='motorista'
            )
            db_session_destino.add(user_destino)
            db_session_destino.flush()  # Gera o ID
            
            # 3.2. Criar Motorista no banco de destino
            motorista_destino = Motorista(
                user_id=user_destino.id,
                nome=motorista.nome,
                cpf_cnpj=motorista.cpf_cnpj,
                email=motorista.email,
                telefone=motorista.telefone,
                endereco=motorista.endereco,
                nro=motorista.nro,
                bairro=motorista.bairro,
                cidade=motorista.cidade,
                uf=motorista.uf,
                chave_pix=motorista.chave_pix,
                status=motorista.status,
                veiculo_nome=motorista.veiculo_nome,
                veiculo_placa=motorista.veiculo_placa,
                veiculo_cor=motorista.veiculo_cor,
                veiculo_ano=motorista.veiculo_ano,
                veiculo_km=motorista.veiculo_km,
                veiculo_obs=motorista.veiculo_obs,
                empresas_acesso=motorista.empresas_acesso,
                empresa_padrao_slug=motorista.empresa_padrao_slug
            )
            db_session_destino.add(motorista_destino)
            db_session_destino.commit()
            
            return (True, f"Motorista criado no banco de {empresa_slug}", motorista_destino)
    
    except IntegrityError as e:
        db_session_destino.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        print(f"[SYNC ERROR] IntegrityError ao sincronizar motorista: {error_msg}")
        
        if 'unique constraint' in error_msg.lower():
            if 'email' in error_msg.lower():
                return (False, f"Email {motorista.email} já existe no banco de {empresa_slug}", None)
            elif 'placa' in error_msg.lower():
                return (False, f"Placa {motorista.veiculo_placa} já existe no banco de {empresa_slug}", None)
        
        return (False, f"Erro de integridade ao sincronizar para {empresa_slug}", None)
    
    except Exception as e:
        db_session_destino.rollback()
        print(f"[SYNC ERROR] Erro ao sincronizar motorista: {str(e)}")
        return (False, f"Erro ao sincronizar para {empresa_slug}: {str(e)}", None)


def sync_motorista_to_all_empresas(motorista, db_session_origem):
    """
    Sincroniza um motorista para todas as empresas listadas em empresas_acesso.
    
    Args:
        motorista: Objeto Motorista do banco de origem
        db_session_origem: SQLAlchemy session do banco de origem
        
    Returns:
        dict: Resultado da sincronização para cada empresa
              Ex: {'nsg': {'success': True, 'message': '...', 'motorista': obj}}
    """
    from app.models import Empresa
    from app.config.db_middleware import get_db_connection
    from sqlalchemy.orm import sessionmaker
    
    resultados = {}
    
    # Verificar se motorista tem empresas_acesso
    if not motorista.empresas_acesso:
        print(f"[SYNC] Motorista {motorista.nome} não tem empresas_acesso definidas. Nada a sincronizar.")
        return resultados
    
    # Parsear empresas_acesso (formato: 'lear,nsg')
    empresas_slugs = [slug.strip() for slug in motorista.empresas_acesso.split(',')]
    
    # Buscar configurações das empresas
    empresas = db_session_origem.query(Empresa).filter(
        Empresa.slug_licenciado.in_(empresas_slugs),
        Empresa.is_banco_local == False  # Apenas empresas remotas
    ).all()
    
    if not empresas:
        print(f"[SYNC] Nenhuma empresa remota encontrada em empresas_acesso: {motorista.empresas_acesso}")
        return resultados
    
    # Sincronizar para cada empresa remota
    for empresa in empresas:
        try:
            print(f"[SYNC] Sincronizando motorista {motorista.nome} para empresa {empresa.slug_licenciado}...")
            
            # Criar conexão com banco remoto
            engine_destino = get_db_connection(empresa)
            Session = sessionmaker(bind=engine_destino)
            db_session_destino = Session()
            
            # Executar sincronização
            success, message, motorista_destino = sync_motorista_to_empresa(
                motorista=motorista,
                empresa_slug=empresa.slug_licenciado,
                db_session_origem=db_session_origem,
                db_session_destino=db_session_destino
            )
            
            resultados[empresa.slug_licenciado] = {
                'success': success,
                'message': message,
                'motorista': motorista_destino
            }
            
            db_session_destino.close()
            
        except Exception as e:
            print(f"[SYNC ERROR] Erro ao sincronizar para {empresa.slug_licenciado}: {str(e)}")
            resultados[empresa.slug_licenciado] = {
                'success': False,
                'message': f"Erro: {str(e)}",
                'motorista': None
            }
    
    return resultados


def remove_motorista_from_empresa(cpf_cnpj, empresa_slug, db_session_destino):
    """
    Remove um motorista do banco de uma empresa específica.
    Usado quando o acesso à empresa é revogado.
    
    Args:
        cpf_cnpj: CPF do motorista
        empresa_slug: Slug da empresa
        db_session_destino: SQLAlchemy session do banco de destino
        
    Returns:
        tuple: (success: bool, message: str)
    """
    from app.models import User, Motorista
    
    try:
        # Buscar motorista por CPF
        motorista = db_session_destino.query(Motorista).filter_by(cpf_cnpj=cpf_cnpj).first()
        
        if not motorista:
            return (True, f"Motorista não existe no banco de {empresa_slug}")
        
        # Remover user associado
        if motorista.user:
            db_session_destino.delete(motorista.user)
        
        # Remover motorista
        db_session_destino.delete(motorista)
        db_session_destino.commit()
        
        print(f"[SYNC] Motorista CPF {cpf_cnpj} removido do banco de {empresa_slug}")
        return (True, f"Motorista removido do banco de {empresa_slug}")
    
    except Exception as e:
        db_session_destino.rollback()
        print(f"[SYNC ERROR] Erro ao remover motorista: {str(e)}")
        return (False, f"Erro ao remover de {empresa_slug}: {str(e)}")
