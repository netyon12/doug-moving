"""
Script de Sincronização Manual de Motoristas
============================================

Este script sincroniza TODOS os motoristas existentes no Banco 1
para os bancos remotos definidos em empresas_acesso.

USO:
----
python sync_all_motoristas.py

IMPORTANTE:
-----------
- Execute este script APÓS instalar os arquivos corrigidos
- Certifique-se de que o servidor Flask NÃO está rodando
- Faça backup do banco de dados antes de executar
"""

import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Motorista
from app.utils.motorista_sync import sync_motorista_to_all_empresas


def sync_all():
    """Sincroniza todos os motoristas com empresas_acesso definidas."""
    
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("SINCRONIZAÇÃO MANUAL DE MOTORISTAS")
        print("="*70 + "\n")
        
        # Buscar todos os motoristas com empresas_acesso
        motoristas = db.session.query(Motorista).filter(
            Motorista.empresas_acesso.isnot(None)
        ).all()
        
        if not motoristas:
            print("⚠️  Nenhum motorista com empresas_acesso encontrado.")
            print("   Certifique-se de que os motoristas têm o campo empresas_acesso preenchido.")
            return
        
        print(f"📋 Encontrados {len(motoristas)} motoristas para sincronizar\n")
        
        total_success = 0
        total_errors = 0
        
        for i, motorista in enumerate(motoristas, 1):
            print(f"[{i}/{len(motoristas)}] Sincronizando {motorista.nome}...")
            print(f"   CPF: {motorista.cpf_cnpj}")
            print(f"   Empresas: {motorista.empresas_acesso}")
            
            if not motorista.cpf_cnpj:
                print("   ⚠️  AVISO: Motorista sem CPF cadastrado. Pulando...")
                total_errors += 1
                print()
                continue
            
            try:
                resultados = sync_motorista_to_all_empresas(motorista, db.session)
                
                if not resultados:
                    print("   ℹ️  Nenhuma empresa remota para sincronizar")
                    print()
                    continue
                
                for empresa_slug, resultado in resultados.items():
                    if resultado['success']:
                        print(f"   ✅ {empresa_slug.upper()}: {resultado['message']}")
                        total_success += 1
                    else:
                        print(f"   ❌ {empresa_slug.upper()}: {resultado['message']}")
                        total_errors += 1
                
                print()
            
            except Exception as e:
                print(f"   ❌ ERRO: {str(e)}")
                total_errors += 1
                print()
        
        print("="*70)
        print("SINCRONIZAÇÃO CONCLUÍDA")
        print("="*70)
        print(f"✅ Sucessos: {total_success}")
        print(f"❌ Erros: {total_errors}")
        print("="*70 + "\n")


if __name__ == '__main__':
    # Confirmação antes de executar
    print("\n⚠️  ATENÇÃO: Este script irá sincronizar todos os motoristas.")
    print("   Certifique-se de que:")
    print("   1. Fez backup do banco de dados")
    print("   2. O servidor Flask NÃO está rodando")
    print("   3. Os arquivos corrigidos foram instalados\n")
    
    resposta = input("Deseja continuar? (s/n): ").lower().strip()
    
    if resposta in ['s', 'sim', 'y', 'yes']:
        sync_all()
    else:
        print("\n❌ Sincronização cancelada pelo usuário.\n")
