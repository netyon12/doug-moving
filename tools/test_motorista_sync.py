"""
Script de Teste: Sincronização de Motoristas Multi-Tenant
==========================================================

Este script testa a funcionalidade de sincronização de motoristas
entre o Banco 1 (principal) e Banco 2 (NSG).

Testes:
-------
1. Verificar se motorista existe no Banco 1
2. Verificar se motorista foi replicado no Banco 2
3. Comparar dados entre os bancos
4. Testar load_user com empresa ativa
"""

import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User, Motorista, Empresa
from app.config.tenant_utils import query_tenant, get_tenant_session
from app.config.db_middleware import get_db_connection
from sqlalchemy.orm import sessionmaker
from flask import session

def test_motorista_sync():
    """Testa sincronização de motoristas entre bancos."""
    
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("TESTE: SINCRONIZAÇÃO DE MOTORISTAS MULTI-TENANT")
        print("="*70 + "\n")
        
        # 1. Buscar motorista Andrea no Banco 1
        print("1. Buscando motorista Andrea no Banco 1...")
        motorista_banco1 = db.session.query(Motorista).filter_by(nome='Andrea').first()
        
        if not motorista_banco1:
            print("❌ Motorista Andrea não encontrado no Banco 1")
            return
        
        print(f"✅ Motorista encontrado no Banco 1:")
        print(f"   - ID: {motorista_banco1.id}")
        print(f"   - Nome: {motorista_banco1.nome}")
        print(f"   - CPF: {motorista_banco1.cpf_cnpj}")
        print(f"   - Email: {motorista_banco1.email}")
        print(f"   - Placa: {motorista_banco1.veiculo_placa}")
        print(f"   - Empresas Acesso: {motorista_banco1.empresas_acesso}")
        print(f"   - User ID: {motorista_banco1.user_id}")
        
        # 2. Buscar empresa NSG
        print("\n2. Buscando configuração da empresa NSG...")
        empresa_nsg = db.session.query(Empresa).filter_by(slug_licenciado='nsg').first()
        
        if not empresa_nsg:
            print("❌ Empresa NSG não encontrada")
            return
        
        print(f"✅ Empresa NSG encontrada:")
        print(f"   - ID: {empresa_nsg.id}")
        print(f"   - Nome: {empresa_nsg.nome}")
        print(f"   - Slug: {empresa_nsg.slug_licenciado}")
        print(f"   - Banco Local: {empresa_nsg.is_banco_local}")
        print(f"   - DB Host: {empresa_nsg.db_host}")
        print(f"   - DB Name: {empresa_nsg.db_name}")
        
        # 3. Conectar ao Banco 2 (NSG)
        print("\n3. Conectando ao Banco 2 (NSG)...")
        try:
            engine_banco2 = get_db_connection(empresa_nsg)
            Session = sessionmaker(bind=engine_banco2)
            db_session_banco2 = Session()
            print("✅ Conexão estabelecida com Banco 2")
        except Exception as e:
            print(f"❌ Erro ao conectar ao Banco 2: {str(e)}")
            return
        
        # 4. Buscar motorista no Banco 2 por CPF
        print("\n4. Buscando motorista Andrea no Banco 2 (por CPF)...")
        motorista_banco2 = db_session_banco2.query(Motorista).filter_by(
            cpf_cnpj=motorista_banco1.cpf_cnpj
        ).first()
        
        if not motorista_banco2:
            print("⚠️  Motorista não encontrado no Banco 2")
            print("   Isso é esperado se a sincronização ainda não foi executada.")
            print("\n5. Executando sincronização manual...")
            
            from app.utils.motorista_sync import sync_motorista_to_all_empresas
            resultados = sync_motorista_to_all_empresas(motorista_banco1, db.session)
            
            for empresa_slug, resultado in resultados.items():
                if resultado['success']:
                    print(f"   ✅ {empresa_slug.upper()}: {resultado['message']}")
                else:
                    print(f"   ❌ {empresa_slug.upper()}: {resultado['message']}")
            
            # Buscar novamente
            motorista_banco2 = db_session_banco2.query(Motorista).filter_by(
                cpf_cnpj=motorista_banco1.cpf_cnpj
            ).first()
        
        if motorista_banco2:
            print(f"\n✅ Motorista encontrado no Banco 2:")
            print(f"   - ID: {motorista_banco2.id}")
            print(f"   - Nome: {motorista_banco2.nome}")
            print(f"   - CPF: {motorista_banco2.cpf_cnpj}")
            print(f"   - Email: {motorista_banco2.email}")
            print(f"   - Placa: {motorista_banco2.veiculo_placa}")
            print(f"   - User ID: {motorista_banco2.user_id}")
            
            # 5. Comparar dados
            print("\n6. Comparando dados entre bancos...")
            campos_diferentes = []
            
            if motorista_banco1.nome != motorista_banco2.nome:
                campos_diferentes.append(f"Nome: '{motorista_banco1.nome}' vs '{motorista_banco2.nome}'")
            if motorista_banco1.cpf_cnpj != motorista_banco2.cpf_cnpj:
                campos_diferentes.append(f"CPF: '{motorista_banco1.cpf_cnpj}' vs '{motorista_banco2.cpf_cnpj}'")
            if motorista_banco1.email != motorista_banco2.email:
                campos_diferentes.append(f"Email: '{motorista_banco1.email}' vs '{motorista_banco2.email}'")
            if motorista_banco1.veiculo_placa != motorista_banco2.veiculo_placa:
                campos_diferentes.append(f"Placa: '{motorista_banco1.veiculo_placa}' vs '{motorista_banco2.veiculo_placa}'")
            
            if campos_diferentes:
                print("⚠️  Diferenças encontradas:")
                for diff in campos_diferentes:
                    print(f"   - {diff}")
            else:
                print("✅ Dados sincronizados corretamente!")
            
            # 6. Testar load_user
            print("\n7. Testando load_user com empresa ativa...")
            
            # Simular sessão com empresa ativa NSG
            with app.test_request_context():
                from flask import session as flask_session
                flask_session['empresa_ativa_slug'] = 'nsg'
                flask_session['empresa_ativa_id'] = empresa_nsg.id
                flask_session['is_banco_local'] = False
                
                # Importar load_user
                from app import login_manager
                
                # Testar com ID do Banco 2
                user_loaded = login_manager.user_loader(motorista_banco2.user_id)
                
                if user_loaded:
                    print(f"✅ load_user retornou usuário:")
                    print(f"   - ID: {user_loaded.id}")
                    print(f"   - Email: {user_loaded.email}")
                    print(f"   - Role: {user_loaded.role}")
                else:
                    print("❌ load_user retornou None")
        
        else:
            print("❌ Motorista não foi sincronizado para o Banco 2")
        
        db_session_banco2.close()
        
        print("\n" + "="*70)
        print("TESTE CONCLUÍDO")
        print("="*70 + "\n")


if __name__ == '__main__':
    test_motorista_sync()
