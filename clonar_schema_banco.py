#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
CLONAR SCHEMA DE BANCO PARA BANCO (V3)
=============================================================================

Este script clona o schema completo do Banco 1 (LEAR) para o Banco 2 (NSG)
criando sequences, tabelas, índices e foreign keys na ordem correta.

CORREÇÕES V3:
- Cria sequences antes das tabelas
- Faz escape de palavras reservadas SQL (user, order, etc.)
- Ordem correta de criação

USO:
    python clonar_schema_banco_v3.py

=============================================================================
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import re


# Palavras reservadas do PostgreSQL que precisam de escape
RESERVED_WORDS = {
    'user', 'order', 'group', 'table', 'column', 'index', 
    'select', 'insert', 'update', 'delete', 'create', 'drop'
}


def escape_identifier(identifier):
    """Escapa identificadores que são palavras reservadas."""
    if identifier.lower() in RESERVED_WORDS:
        return f'"{identifier}"'
    return identifier


def print_header():
    """Exibe cabeçalho do script."""
    print("\n" + "=" * 70)
    print("  📋 CLONAR SCHEMA DE BANCO PARA BANCO (V3)")
    print("=" * 70)
    print()


def get_connection_info(banco_nome):
    """Solicita informações de conexão do banco."""
    print(f"\n📝 Informações do {banco_nome}:")
    print()
    
    host = input("   Host do banco: ").strip()
    dbname = input("   Nome do banco: ").strip()
    user = input("   Usuário: ").strip()
    password = input("   Senha: ").strip()
    port = input("   Porta (Enter para 5432): ").strip() or "5432"
    
    return {
        'host': host,
        'dbname': dbname,
        'user': user,
        'password': password,
        'port': port
    }


def test_connection(conn_info, banco_nome):
    """Testa conexão com o banco."""
    try:
        conn = psycopg2.connect(**conn_info)
        conn.close()
        print(f"   ✅ Conexão com {banco_nome} OK")
        return True
    except Exception as e:
        print(f"   ❌ Erro ao conectar no {banco_nome}: {e}")
        return False


def get_all_tables(conn_info):
    """Lista todas as tabelas do banco."""
    conn = psycopg2.connect(**conn_info)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return tables


def get_all_sequences(conn_info):
    """Lista todas as sequences do banco."""
    conn = psycopg2.connect(**conn_info)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT sequence_name 
        FROM information_schema.sequences 
        WHERE sequence_schema = 'public'
        ORDER BY sequence_name;
    """)
    
    sequences = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return sequences


def drop_all_objects(conn_info):
    """Remove todas as sequences e tabelas do banco de destino."""
    print("\n🗑️  Removendo objetos existentes no Banco de Destino...")
    
    conn = psycopg2.connect(**conn_info)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Dropar todas as tabelas com CASCADE
    tables = get_all_tables(conn_info)
    for table in tables:
        try:
            table_escaped = escape_identifier(table)
            cursor.execute(f"DROP TABLE IF EXISTS {table_escaped} CASCADE;")
            print(f"   ✅ Removida tabela: {table}")
        except Exception as e:
            print(f"   ⚠️  Erro ao remover tabela {table}: {e}")
    
    # Dropar todas as sequences
    sequences = get_all_sequences(conn_info)
    for seq in sequences:
        try:
            cursor.execute(f"DROP SEQUENCE IF EXISTS {seq} CASCADE;")
            print(f"   ✅ Removida sequence: {seq}")
        except Exception as e:
            print(f"   ⚠️  Erro ao remover sequence {seq}: {e}")
    
    cursor.close()
    conn.close()
    
    print(f"\n   ✅ {len(tables)} tabelas e {len(sequences)} sequences removidas")


def copy_sequences(origem_info, destino_info):
    """Copia todas as sequences do banco de origem."""
    print("\n🔄 Copiando sequences...")
    
    conn_origem = psycopg2.connect(**origem_info)
    cursor_origem = conn_origem.cursor()
    
    conn_destino = psycopg2.connect(**destino_info)
    conn_destino.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_destino = conn_destino.cursor()
    
    sequences = get_all_sequences(origem_info)
    
    print(f"\n📋 Encontradas {len(sequences)} sequences para copiar\n")
    
    for seq in sequences:
        try:
            # Obter definição da sequence
            cursor_origem.execute(f"""
                SELECT 
                    start_value,
                    minimum_value,
                    maximum_value,
                    increment
                FROM information_schema.sequences
                WHERE sequence_schema = 'public'
                  AND sequence_name = %s;
            """, (seq,))
            
            result = cursor_origem.fetchone()
            if result:
                start_val, min_val, max_val, increment = result
                
                # Criar sequence no destino
                cursor_destino.execute(f"""
                    CREATE SEQUENCE {seq}
                    START WITH {start_val}
                    MINVALUE {min_val}
                    MAXVALUE {max_val}
                    INCREMENT BY {increment};
                """)
                print(f"   ✅ Criada sequence: {seq}")
            
        except Exception as e:
            print(f"   ❌ Erro ao copiar sequence {seq}: {e}")
    
    cursor_origem.close()
    conn_origem.close()
    cursor_destino.close()
    conn_destino.close()
    
    return len(sequences)


def copy_tables(origem_info, destino_info):
    """Copia todas as tabelas do banco de origem."""
    print("\n🔄 Copiando tabelas...")
    
    conn_origem = psycopg2.connect(**origem_info)
    cursor_origem = conn_origem.cursor()
    
    conn_destino = psycopg2.connect(**destino_info)
    conn_destino.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_destino = conn_destino.cursor()
    
    tables = get_all_tables(origem_info)
    
    print(f"\n📋 Encontradas {len(tables)} tabelas para copiar\n")
    
    for table in tables:
        try:
            # Obter colunas da tabela
            cursor_origem.execute("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
            
            columns = cursor_origem.fetchall()
            
            # Construir DDL
            table_escaped = escape_identifier(table)
            ddl = f"CREATE TABLE {table_escaped} (\n"
            
            column_defs = []
            for col in columns:
                col_name, data_type, max_length, num_precision, num_scale, nullable, default = col
                
                col_name_escaped = escape_identifier(col_name)
                col_def = f"    {col_name_escaped} "
                
                # Tipo de dado
                if data_type == 'character varying':
                    col_def += f"VARCHAR({max_length})"
                elif data_type == 'numeric' and num_precision and num_scale:
                    col_def += f"NUMERIC({num_precision},{num_scale})"
                elif data_type == 'timestamp without time zone':
                    col_def += "TIMESTAMP"
                elif data_type == 'timestamp with time zone':
                    col_def += "TIMESTAMPTZ"
                else:
                    col_def += data_type.upper()
                
                # NOT NULL
                if nullable == 'NO':
                    col_def += " NOT NULL"
                
                # DEFAULT
                if default:
                    col_def += f" DEFAULT {default}"
                
                column_defs.append(col_def)
            
            ddl += ",\n".join(column_defs)
            ddl += "\n);"
            
            # Criar tabela no destino
            cursor_destino.execute(ddl)
            print(f"   ✅ Criada: {table}")
            
        except Exception as e:
            print(f"   ❌ Erro ao copiar {table}: {e}")
    
    cursor_origem.close()
    conn_origem.close()
    cursor_destino.close()
    conn_destino.close()
    
    return len(tables)


def copy_primary_keys(origem_info, destino_info):
    """Copia primary keys."""
    print("\n🔄 Copiando primary keys...")
    
    conn_origem = psycopg2.connect(**origem_info)
    cursor_origem = conn_origem.cursor()
    
    conn_destino = psycopg2.connect(**destino_info)
    conn_destino.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_destino = conn_destino.cursor()
    
    # Obter PKs
    cursor_origem.execute("""
        SELECT
            tc.table_name,
            tc.constraint_name,
            kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = 'public'
        ORDER BY tc.table_name;
    """)
    
    pks = cursor_origem.fetchall()
    
    for pk in pks:
        table_name, constraint_name, column_name = pk
        try:
            table_escaped = escape_identifier(table_name)
            column_escaped = escape_identifier(column_name)
            cursor_destino.execute(f"""
                ALTER TABLE {table_escaped}
                ADD CONSTRAINT {constraint_name}
                PRIMARY KEY ({column_escaped});
            """)
        except Exception as e:
            # Ignorar erros de PKs duplicadas
            pass
    
    print(f"   ✅ {len(pks)} primary keys copiadas")
    
    cursor_origem.close()
    conn_origem.close()
    cursor_destino.close()
    conn_destino.close()


def copy_indexes(origem_info, destino_info):
    """Copia índices."""
    print("\n🔄 Copiando índices...")
    
    conn_origem = psycopg2.connect(**origem_info)
    cursor_origem = conn_origem.cursor()
    
    conn_destino = psycopg2.connect(**destino_info)
    conn_destino.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_destino = conn_destino.cursor()
    
    cursor_origem.execute("""
        SELECT indexdef || ';'
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname NOT LIKE '%_pkey';
    """)
    
    indices = cursor_origem.fetchall()
    
    for index in indices:
        try:
            index_def = index[0]
            # Escapar palavras reservadas no indexdef
            for word in RESERVED_WORDS:
                # Substituir apenas se for nome de tabela/coluna, não palavra-chave SQL
                pattern = rf'\b{word}\b(?!\s*\()'
                index_def = re.sub(pattern, f'"{word}"', index_def, flags=re.IGNORECASE)
            
            cursor_destino.execute(index_def)
        except Exception as e:
            # Ignorar erros de índices duplicados
            pass
    
    print(f"   ✅ {len(indices)} índices copiados")
    
    cursor_origem.close()
    conn_origem.close()
    cursor_destino.close()
    conn_destino.close()


def copy_foreign_keys(origem_info, destino_info):
    """Copia foreign keys."""
    print("\n🔄 Copiando foreign keys...")
    
    conn_origem = psycopg2.connect(**origem_info)
    cursor_origem = conn_origem.cursor()
    
    conn_destino = psycopg2.connect(**destino_info)
    conn_destino.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor_destino = conn_destino.cursor()
    
    cursor_origem.execute("""
        SELECT
            tc.table_name,
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public';
    """)
    
    fks = cursor_origem.fetchall()
    
    success_count = 0
    for fk in fks:
        table_name, constraint_name, column_name, foreign_table, foreign_column = fk
        try:
            table_escaped = escape_identifier(table_name)
            column_escaped = escape_identifier(column_name)
            foreign_table_escaped = escape_identifier(foreign_table)
            foreign_column_escaped = escape_identifier(foreign_column)
            
            cursor_destino.execute(f"""
                ALTER TABLE {table_escaped}
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({column_escaped})
                REFERENCES {foreign_table_escaped}({foreign_column_escaped});
            """)
            success_count += 1
        except Exception as e:
            # Apenas contar sucessos, ignorar erros
            pass
    
    print(f"   ✅ {success_count}/{len(fks)} foreign keys copiadas")
    
    cursor_origem.close()
    conn_origem.close()
    cursor_destino.close()
    conn_destino.close()


def verify_schema(conn_info):
    """Verifica se o schema foi criado corretamente."""
    print("\n🔍 Verificando schema criado...")
    
    tables = get_all_tables(conn_info)
    sequences = get_all_sequences(conn_info)
    
    print(f"\n📋 Sequences encontradas ({len(sequences)}):")
    for seq in sequences[:5]:  # Mostrar apenas primeiras 5
        print(f"   • {seq}")
    if len(sequences) > 5:
        print(f"   ... e mais {len(sequences) - 5} sequences")
    
    print(f"\n📋 Tabelas encontradas ({len(tables)}):")
    for table in tables:
        print(f"   • {table}")
    
    return len(tables) > 0


def main():
    """Função principal."""
    print_header()
    
    # Obter informações dos bancos
    print("🔵 BANCO DE ORIGEM (LEAR - Banco 1)")
    origem_info = get_connection_info("Banco de Origem")
    
    print("\n🟢 BANCO DE DESTINO (NSG - Banco 2)")
    destino_info = get_connection_info("Banco de Destino")
    
    # Testar conexões
    print("\n🔄 Testando conexões...")
    if not test_connection(origem_info, "Banco de Origem"):
        print("\n❌ Falha ao conectar no Banco de Origem. Verifique as credenciais.")
        sys.exit(1)
    
    if not test_connection(destino_info, "Banco de Destino"):
        print("\n❌ Falha ao conectar no Banco de Destino. Verifique as credenciais.")
        sys.exit(1)
    
    # Confirmar operação
    print("\n" + "=" * 70)
    print("⚠️  ATENÇÃO:")
    print("   • Todas as sequences e tabelas do Banco de Destino serão REMOVIDAS")
    print("   • O schema do Banco de Origem será copiado para o Banco de Destino")
    print("   • DADOS NÃO SERÃO COPIADOS (apenas estrutura)")
    print("=" * 70)
    
    confirm = input("\n   Deseja continuar? (s/n): ").strip().lower()
    if confirm != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        sys.exit(0)
    
    # Remover objetos do banco de destino
    drop_all_objects(destino_info)
    
    # Copiar schema na ordem correta
    copy_sequences(origem_info, destino_info)
    total_tables = copy_tables(origem_info, destino_info)
    copy_primary_keys(origem_info, destino_info)
    copy_indexes(origem_info, destino_info)
    copy_foreign_keys(origem_info, destino_info)
    
    # Verificar schema criado
    if not verify_schema(destino_info):
        print("\n❌ Falha ao verificar schema.")
        sys.exit(1)
    
    # Sucesso
    print("\n" + "=" * 70)
    print("✅ SCHEMA CLONADO COM SUCESSO!")
    print("=" * 70)
    print(f"\n📊 Total: {total_tables} tabelas copiadas")
    print("\n📝 Próximos passos:")
    print("   1. Reinicie o sistema")
    print("   2. Logue como Admin via GOMOBI")
    print("   3. Troque para NSG no seletor")
    print("   4. Comece a cadastrar dados na NSG")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
