#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MIGRAÇÃO DE QUERIES PARA MULTI-TENANT - DASHBOARD
=============================================================================

Este script migra queries do padrão Model.query para query_tenant(Model)
especificamente nos arquivos do dashboard que foram esquecidos na migração
inicial.

Arquivos a migrar:
- app/blueprints/dashboard/dashboard.py
- app/blueprints/dashboard/dash_operacional.py
- app/blueprints/dashboard/dash_executivo.py
- app/blueprints/dashboard/dash_utils.py
- app/blueprints/dashboard/dash_graficos.py

USO:
    python migrar_dashboard_tenant.py

=============================================================================
"""

import re
import os
from pathlib import Path


# Arquivos do dashboard para migrar
ARQUIVOS_DASHBOARD = [
    'app/blueprints/dashboard/dashboard.py',
    'app/blueprints/dashboard/dash_operacional.py',
    'app/blueprints/dashboard/dash_executivo.py',
    'app/blueprints/dashboard/dash_utils.py',
    'app/blueprints/dashboard/dash_graficos.py',
]


def adicionar_import(conteudo):
    """
    Adiciona import de query_tenant se não existir.
    """
    if 'from app.config.tenant_utils import' in conteudo:
        # Já tem import, verificar se tem query_tenant
        if 'query_tenant' not in conteudo:
            # Adicionar query_tenant ao import existente
            conteudo = re.sub(
                r'from app\.config\.tenant_utils import ([^\n]+)',
                r'from app.config.tenant_utils import \1, query_tenant',
                conteudo
            )
    else:
        # Adicionar import completo após os imports do Flask
        linhas = conteudo.split('\n')
        nova_linhas = []
        import_adicionado = False
        
        for i, linha in enumerate(linhas):
            nova_linhas.append(linha)
            
            # Adicionar após imports do Flask/Flask-Login
            if not import_adicionado and linha.startswith('from flask'):
                # Verificar se próxima linha também é import do Flask
                if i + 1 < len(linhas) and not linhas[i + 1].startswith('from flask'):
                    nova_linhas.append('')
                    nova_linhas.append('from app.config.tenant_utils import query_tenant')
                    import_adicionado = True
        
        if not import_adicionado:
            # Se não encontrou lugar ideal, adicionar após imports do app
            nova_linhas_2 = []
            for i, linha in enumerate(nova_linhas):
                nova_linhas_2.append(linha)
                if not import_adicionado and linha.startswith('from app import'):
                    if i + 1 < len(nova_linhas) and not nova_linhas[i + 1].startswith('from app'):
                        nova_linhas_2.append('')
                        nova_linhas_2.append('from app.config.tenant_utils import query_tenant')
                        import_adicionado = True
            
            if import_adicionado:
                conteudo = '\n'.join(nova_linhas_2)
            else:
                conteudo = '\n'.join(nova_linhas)
        else:
            conteudo = '\n'.join(nova_linhas)
    
    return conteudo


def migrar_queries(conteudo):
    """
    Migra queries de Model.query para query_tenant(Model).
    """
    # Padrão: Model.query.método(...)
    # Captura o nome do modelo e preserva o resto da query
    
    # Lista de modelos conhecidos
    modelos = [
        'Empresa', 'Planta', 'CentroCusto', 'Turno', 'Bloco', 'Bairro',
        'Gerente', 'Supervisor', 'Colaborador', 'Motorista',
        'Viagem', 'Solicitacao', 'ViagemHoraParada',
        'User', 'Configuracao', 'Logs',
        'FinContasPagar', 'FinContasReceber', 'Fretado'
    ]
    
    contador = 0
    
    for modelo in modelos:
        # Padrão: Modelo.query.método
        padrao = rf'\b{modelo}\.query\b'
        
        # Contar ocorrências
        ocorrencias = len(re.findall(padrao, conteudo))
        if ocorrencias > 0:
            contador += ocorrencias
            # Substituir
            conteudo = re.sub(padrao, f'query_tenant({modelo})', conteudo)
    
    return conteudo, contador


def processar_arquivo(caminho_arquivo):
    """
    Processa um arquivo, migrando queries e adicionando imports.
    """
    print(f"\n📄 Processando: {caminho_arquivo}")
    
    if not os.path.exists(caminho_arquivo):
        print(f"   ⚠️  Arquivo não encontrado: {caminho_arquivo}")
        return 0
    
    # Ler conteúdo
    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        conteudo_original = f.read()
    
    # Migrar queries
    conteudo_migrado, total_migracoes = migrar_queries(conteudo_original)
    
    if total_migracoes == 0:
        print(f"   ℹ️  Nenhuma query para migrar")
        return 0
    
    # Adicionar import
    conteudo_final = adicionar_import(conteudo_migrado)
    
    # Salvar arquivo
    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        f.write(conteudo_final)
    
    print(f"   ✅ {total_migracoes} queries migradas")
    
    return total_migracoes


def main():
    """
    Função principal.
    """
    print("\n" + "=" * 70)
    print("  📋 MIGRAÇÃO DE QUERIES PARA MULTI-TENANT - DASHBOARD")
    print("=" * 70)
    
    total_geral = 0
    arquivos_processados = 0
    
    for arquivo in ARQUIVOS_DASHBOARD:
        total = processar_arquivo(arquivo)
        if total > 0:
            arquivos_processados += 1
            total_geral += total
    
    print("\n" + "=" * 70)
    print("✅ MIGRAÇÃO CONCLUÍDA!")
    print("=" * 70)
    print(f"\n📊 Estatísticas:")
    print(f"   • Arquivos processados: {arquivos_processados}/{len(ARQUIVOS_DASHBOARD)}")
    print(f"   • Total de queries migradas: {total_geral}")
    
    print("\n📝 Próximos passos:")
    print("   1. Reinicie a aplicação")
    print("   2. Logue como Admin via GOMOBI")
    print("   3. Troque para NSG no seletor")
    print("   4. Verifique se dashboard mostra dados corretos (vazios para NSG)")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário.")
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
