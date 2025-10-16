"""
Script para aplicar a migration do modelo Fretado.

Este script:
1. Cria a tabela 'fretado' no banco de dados
2. Adiciona o campo 'fretado_id' na tabela 'solicitacao'
3. Insere a configuração 'limite_fretado' com valor padrão 9
4. Cria índices para melhor performance

Compatível com SQLite (desenvolvimento) e PostgreSQL (produção).
"""

from app import create_app, db
from app.models import Configuracao
from sqlalchemy import text, inspect
import os

def verificar_coluna_existe(tabela, coluna):
    """Verifica se uma coluna existe em uma tabela."""
    inspector = inspect(db.engine)
    colunas = [col['name'] for col in inspector.get_columns(tabela)]
    return coluna in colunas

def verificar_tabela_existe(tabela):
    """Verifica se uma tabela existe no banco de dados."""
    inspector = inspect(db.engine)
    return tabela in inspector.get_table_names()

def aplicar_migration():
    """Aplica a migration do Fretado."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("MIGRATION: Implementação do modelo Fretado")
        print("=" * 80)
        
        # Detectar tipo de banco de dados
        db_url = os.environ.get('DATABASE_URL', 'sqlite:///doug_moving.db')
        is_postgres = 'postgresql' in db_url
        
        print(f"\n📊 Banco de dados: {'PostgreSQL' if is_postgres else 'SQLite'}")
        
        try:
            # 1. Criar tabela fretado
            print("\n1️⃣ Criando tabela 'fretado'...")
            if not verificar_tabela_existe('fretado'):
                if is_postgres:
                    # PostgreSQL usa SERIAL ao invés de AUTOINCREMENT
                    sql_create_fretado = text("""
                        CREATE TABLE fretado (
                            id SERIAL PRIMARY KEY,
                            empresa_id INTEGER NOT NULL,
                            planta_id INTEGER NOT NULL,
                            bloco_id INTEGER,
                            blocos_ids VARCHAR(255),
                            grupo_bloco VARCHAR(50),
                            tipo_linha VARCHAR(10) NOT NULL,
                            tipo_corrida VARCHAR(20) NOT NULL,
                            horario_entrada TIMESTAMP,
                            horario_saida TIMESTAMP,
                            horario_desligamento TIMESTAMP,
                            colaboradores_ids TEXT,
                            quantidade_passageiros INTEGER DEFAULT 0,
                            valor NUMERIC(10, 2),
                            valor_repasse NUMERIC(10, 2),
                            status VARCHAR(20) NOT NULL DEFAULT 'Fretado',
                            observacoes TEXT,
                            created_by_user_id INTEGER,
                            data_criacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            data_atualizacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (empresa_id) REFERENCES empresa (id),
                            FOREIGN KEY (planta_id) REFERENCES planta (id),
                            FOREIGN KEY (bloco_id) REFERENCES bloco (id),
                            FOREIGN KEY (created_by_user_id) REFERENCES "user" (id)
                        )
                    """)
                else:
                    # SQLite
                    sql_create_fretado = text("""
                        CREATE TABLE fretado (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            empresa_id INTEGER NOT NULL,
                            planta_id INTEGER NOT NULL,
                            bloco_id INTEGER,
                            blocos_ids VARCHAR(255),
                            grupo_bloco VARCHAR(50),
                            tipo_linha VARCHAR(10) NOT NULL,
                            tipo_corrida VARCHAR(20) NOT NULL,
                            horario_entrada DATETIME,
                            horario_saida DATETIME,
                            horario_desligamento DATETIME,
                            colaboradores_ids TEXT,
                            quantidade_passageiros INTEGER DEFAULT 0,
                            valor NUMERIC(10, 2),
                            valor_repasse NUMERIC(10, 2),
                            status VARCHAR(20) NOT NULL DEFAULT 'Fretado',
                            observacoes TEXT,
                            created_by_user_id INTEGER,
                            data_criacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            data_atualizacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (empresa_id) REFERENCES empresa (id),
                            FOREIGN KEY (planta_id) REFERENCES planta (id),
                            FOREIGN KEY (bloco_id) REFERENCES bloco (id),
                            FOREIGN KEY (created_by_user_id) REFERENCES user (id)
                        )
                    """)
                
                db.session.execute(sql_create_fretado)
                db.session.commit()
                print("   ✅ Tabela 'fretado' criada com sucesso!")
            else:
                print("   ⚠️  Tabela 'fretado' já existe. Pulando...")
            
            # 2. Adicionar campo fretado_id na tabela solicitacao
            print("\n2️⃣ Adicionando campo 'fretado_id' na tabela 'solicitacao'...")
            if not verificar_coluna_existe('solicitacao', 'fretado_id'):
                sql_add_column = text("""
                    ALTER TABLE solicitacao 
                    ADD COLUMN fretado_id INTEGER REFERENCES fretado(id)
                """)
                db.session.execute(sql_add_column)
                db.session.commit()
                print("   ✅ Campo 'fretado_id' adicionado com sucesso!")
            else:
                print("   ⚠️  Campo 'fretado_id' já existe. Pulando...")
            
            # 3. Inserir configuração para limite de fretado
            print("\n3️⃣ Configurando limite de fretado...")
            config_existente = Configuracao.query.filter_by(chave='limite_fretado').first()
            if not config_existente:
                nova_config = Configuracao(chave='limite_fretado', valor='9')
                db.session.add(nova_config)
                db.session.commit()
                print("   ✅ Configuração 'limite_fretado' criada com valor padrão: 9")
            else:
                print(f"   ⚠️  Configuração 'limite_fretado' já existe com valor: {config_existente.valor}")
            
            # 4. Criar índices
            print("\n4️⃣ Criando índices para melhor performance...")
            indices = [
                ("idx_fretado_empresa", "CREATE INDEX IF NOT EXISTS idx_fretado_empresa ON fretado(empresa_id)"),
                ("idx_fretado_planta", "CREATE INDEX IF NOT EXISTS idx_fretado_planta ON fretado(planta_id)"),
                ("idx_fretado_grupo_bloco", "CREATE INDEX IF NOT EXISTS idx_fretado_grupo_bloco ON fretado(grupo_bloco)"),
                ("idx_fretado_data_criacao", "CREATE INDEX IF NOT EXISTS idx_fretado_data_criacao ON fretado(data_criacao)"),
                ("idx_solicitacao_fretado", "CREATE INDEX IF NOT EXISTS idx_solicitacao_fretado ON solicitacao(fretado_id)")
            ]
            
            for nome_indice, sql_indice in indices:
                try:
                    db.session.execute(text(sql_indice))
                    print(f"   ✅ Índice '{nome_indice}' criado!")
                except Exception as e:
                    print(f"   ⚠️  Índice '{nome_indice}' já existe ou erro: {str(e)}")
            
            db.session.commit()
            
            print("\n" + "=" * 80)
            print("✅ MIGRATION CONCLUÍDA COM SUCESSO!")
            print("=" * 80)
            print("\n📋 Resumo:")
            print("   • Tabela 'fretado' criada")
            print("   • Campo 'fretado_id' adicionado em 'solicitacao'")
            print("   • Configuração 'limite_fretado' = 9")
            print("   • Índices criados para otimização")
            print("\n🚀 O sistema está pronto para o novo processo de Fretados!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERRO ao aplicar migration: {str(e)}")
            print("\nDetalhes do erro:")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    sucesso = aplicar_migration()
    exit(0 if sucesso else 1)

