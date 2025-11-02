"""
Script de Migração - Adicionar Índices para Performance
Sistema Go Mobi

Este script adiciona índices nas colunas mais consultadas para melhorar
a performance de queries, especialmente em relatórios e dashboards.

IMPORTANTE: Execute este script APENAS UMA VEZ em cada ambiente.
"""

from app import create_app, db
from sqlalchemy import text

def adicionar_indices():
    """Adiciona índices no banco de dados para melhorar performance."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("ADICIONANDO ÍNDICES NO BANCO DE DADOS")
        print("=" * 70)
        
        indices = [
            # TABELA: solicitacao
            ("idx_solicitacao_empresa", "solicitacao", "empresa_id"),
            ("idx_solicitacao_planta", "solicitacao", "planta_id"),
            ("idx_solicitacao_colaborador", "solicitacao", "colaborador_id"),
            ("idx_solicitacao_supervisor", "solicitacao", "supervisor_id"),
            ("idx_solicitacao_bloco", "solicitacao", "bloco_id"),
            ("idx_solicitacao_status", "solicitacao", "status"),
            ("idx_solicitacao_data_criacao", "solicitacao", "data_criacao"),
            ("idx_solicitacao_tipo_corrida", "solicitacao", "tipo_corrida"),
            ("idx_solicitacao_tipo_linha", "solicitacao", "tipo_linha"),
            
            # TABELA: viagem
            ("idx_viagem_empresa", "viagem", "empresa_id"),
            ("idx_viagem_planta", "viagem", "planta_id"),
            ("idx_viagem_bloco", "viagem", "bloco_id"),
            ("idx_viagem_motorista", "viagem", "motorista_id"),
            ("idx_viagem_status", "viagem", "status"),
            ("idx_viagem_horario_entrada", "viagem", "horario_entrada"),
            ("idx_viagem_horario_saida", "viagem", "horario_saida"),
            ("idx_viagem_horario_desligamento", "viagem", "horario_desligamento"),
            ("idx_viagem_data_criacao", "viagem", "data_criacao"),
            ("idx_viagem_tipo_corrida", "viagem", "tipo_corrida"),
            ("idx_viagem_tipo_linha", "viagem", "tipo_linha"),
            
            # TABELA: colaborador
            ("idx_colaborador_empresa", "colaborador", "empresa_id"),
            ("idx_colaborador_planta", "colaborador", "planta_id"),
            ("idx_colaborador_status", "colaborador", "status"),
            ("idx_colaborador_cpf", "colaborador", "cpf"),
            
            # TABELA: motorista
            ("idx_motorista_status_disponibilidade", "motorista", "status_disponibilidade"),
            ("idx_motorista_cpf", "motorista", "cpf"),
            
            # TABELA: fretado
            ("idx_fretado_empresa", "fretado", "empresa_id"),
            ("idx_fretado_planta", "fretado", "planta_id"),
            ("idx_fretado_motorista", "fretado", "motorista_id"),
            ("idx_fretado_status", "fretado", "status"),
            ("idx_fretado_data_criacao", "fretado", "data_criacao"),
        ]
        
        indices_criados = 0
        indices_existentes = 0
        indices_erro = 0
        
        for nome_indice, tabela, coluna in indices:
            try:
                # Verificar se o índice já existe
                check_query = text(f"""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE indexname = :nome_indice
                """)
                result = db.session.execute(check_query, {"nome_indice": nome_indice})
                existe = result.scalar() > 0
                
                if existe:
                    print(f"⏭️  {nome_indice} - JÁ EXISTE")
                    indices_existentes += 1
                else:
                    # Criar índice
                    create_query = text(f"""
                        CREATE INDEX {nome_indice} ON {tabela} ({coluna})
                    """)
                    db.session.execute(create_query)
                    db.session.commit()
                    print(f"✅ {nome_indice} - CRIADO")
                    indices_criados += 1
                    
            except Exception as e:
                print(f"❌ {nome_indice} - ERRO: {str(e)}")
                indices_erro += 1
                db.session.rollback()
        
        print("\n" + "=" * 70)
        print("RESUMO")
        print("=" * 70)
        print(f"✅ Índices criados: {indices_criados}")
        print(f"⏭️  Índices já existentes: {indices_existentes}")
        print(f"❌ Erros: {indices_erro}")
        print(f"📊 Total processado: {len(indices)}")
        print("=" * 70)
        
        if indices_erro == 0:
            print("\n🎉 SUCESSO! Todos os índices foram processados corretamente.")
            print("⚡ Performance de queries deve melhorar significativamente!")
        else:
            print(f"\n⚠️  ATENÇÃO: {indices_erro} índice(s) com erro. Verifique os logs acima.")

if __name__ == '__main__':
    adicionar_indices()
