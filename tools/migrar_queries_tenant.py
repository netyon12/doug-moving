#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MIGRAR QUERIES PARA MULTI-TENANT
=============================================================================

Este script migra automaticamente as queries dos blueprints para usar
query_tenant() ao invés de Model.query.

USO:
    python migrar_queries_tenant.py

O script irá:
    1. Fazer backup dos arquivos originais
    2. Identificar todas as queries
    3. Substituir por query_tenant()
    4. Adicionar imports necessários
    5. Gerar relatório de alterações

=============================================================================
"""

import os
import re
import shutil
from datetime import datetime


def print_header():
    """Exibe cabeçalho do script."""
    print("\n" + "=" * 70)
    print("  🔄 MIGRAR QUERIES PARA MULTI-TENANT")
    print("=" * 70)
    print()


def backup_file(filepath):
    """Cria backup do arquivo original."""
    backup_dir = os.path.join(os.path.dirname(filepath), '_backup_queries')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.basename(filepath)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    
    shutil.copy2(filepath, backup_path)
    return backup_path


def has_tenant_import(content):
    """Verifica se o arquivo já tem o import de query_tenant."""
    return 'from app.config.tenant_utils import' in content


def add_tenant_import(content):
    """Adiciona import de query_tenant no arquivo."""
    # Procurar a linha de import do db
    db_import_pattern = r'from \.\. import db'
    
    if re.search(db_import_pattern, content):
        # Adicionar import após o import do db
        new_import = 'from ..config.tenant_utils import query_tenant, get_tenant_session'
        content = re.sub(
            db_import_pattern,
            r'from .. import db\n' + new_import,
            content,
            count=1
        )
    else:
        # Adicionar no início dos imports
        lines = content.split('\n')
        import_index = 0
        for i, line in enumerate(lines):
            if line.startswith('from') or line.startswith('import'):
                import_index = i + 1
        
        lines.insert(import_index, 'from app.config.tenant_utils import query_tenant, get_tenant_session')
        content = '\n'.join(lines)
    
    return content


def migrate_queries(content):
    """Migra queries para usar query_tenant()."""
    changes = []
    
    # Padrão: Model.query.método()
    # Exemplos: Solicitacao.query.filter(), Viagem.query.get()
    pattern = r'(\w+)\.query\.'
    
    def replace_query(match):
        model_name = match.group(1)
        changes.append(f"{model_name}.query → query_tenant({model_name})")
        return f'query_tenant({model_name}).'
    
    new_content = re.sub(pattern, replace_query, content)
    
    return new_content, changes


def migrate_db_session(content):
    """Migra db.session para get_tenant_session()."""
    changes = []
    
    # Substituir db.session por get_tenant_session()
    if 'db.session' in content:
        content = content.replace('db.session', 'get_tenant_session()')
        changes.append('db.session → get_tenant_session()')
    
    return content, changes


def process_file(filepath):
    """Processa um arquivo Python."""
    print(f"\n📝 Processando: {os.path.basename(filepath)}")
    
    # Ler conteúdo
    with open(filepath, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Verificar se já foi migrado
    if has_tenant_import(original_content):
        print("   ⚠️  Arquivo já foi migrado anteriormente")
        return None
    
    # Fazer backup
    backup_path = backup_file(filepath)
    print(f"   💾 Backup: {os.path.basename(backup_path)}")
    
    # Adicionar import
    content = add_tenant_import(original_content)
    
    # Migrar queries
    content, query_changes = migrate_queries(content)
    
    # Migrar db.session
    content, session_changes = migrate_db_session(content)
    
    all_changes = query_changes + session_changes
    
    if not all_changes:
        print("   ℹ️  Nenhuma query encontrada para migrar")
        return None
    
    # Salvar arquivo modificado
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"   ✅ Migrado: {len(all_changes)} alterações")
    
    return {
        'file': os.path.basename(filepath),
        'changes': all_changes,
        'backup': backup_path
    }


def generate_report(results):
    """Gera relatório das migrações."""
    print("\n" + "=" * 70)
    print("  📊 RELATÓRIO DE MIGRAÇÃO")
    print("=" * 70)
    
    total_files = len([r for r in results if r])
    total_changes = sum(len(r['changes']) for r in results if r)
    
    print(f"\n✅ Arquivos migrados: {total_files}")
    print(f"✅ Total de alterações: {total_changes}")
    
    print("\n📋 Detalhes por arquivo:")
    for result in results:
        if result:
            print(f"\n   📄 {result['file']}")
            print(f"      Alterações: {len(result['changes'])}")
            print(f"      Backup: {os.path.basename(result['backup'])}")
    
    print("\n" + "=" * 70)


def main():
    """Função principal."""
    print_header()
    
    # Lista de arquivos para migrar
    blueprints_dir = 'app/blueprints'
    
    files_to_migrate = [
        os.path.join(blueprints_dir, 'solicitacoes.py'),
        os.path.join(blueprints_dir, 'viagens.py'),
        os.path.join(blueprints_dir, 'agrupamento.py'),
        os.path.join(blueprints_dir, 'cadastros.py'),
        os.path.join(blueprints_dir, 'colaboradores.py'),
        os.path.join(blueprints_dir, 'motorista.py'),
        os.path.join(blueprints_dir, 'relatorios.py'),
        os.path.join(blueprints_dir, 'dashboard/dash_main.py'),
        os.path.join(blueprints_dir, 'dashboard/dash_graficos.py'),
    ]
    
    # Filtrar apenas arquivos que existem
    existing_files = [f for f in files_to_migrate if os.path.exists(f)]
    
    print(f"📁 Arquivos encontrados: {len(existing_files)}")
    print("\n⚠️  ATENÇÃO: Este script irá modificar os arquivos!")
    print("   Backups serão criados em app/blueprints/_backup_queries/")
    
    confirm = input("\n   Deseja continuar? (s/n): ").strip().lower()
    if confirm != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        return
    
    # Processar arquivos
    results = []
    for filepath in existing_files:
        result = process_file(filepath)
        results.append(result)
    
    # Gerar relatório
    generate_report(results)
    
    print("\n✅ Migração concluída!")
    print("\n📝 Próximos passos:")
    print("   1. Teste o sistema localmente")
    print("   2. Verifique se as queries estão funcionando")
    print("   3. Se houver problemas, restaure os backups")
    print()


if __name__ == '__main__':
    main()
