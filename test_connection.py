# test_connection.py
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

# Carrega .env (não .env.local)
load_dotenv('.env')

database_url = os.getenv('DATABASE_URL')

if not database_url:
    print("❌ DATABASE_URL não configurado no .env!")
    exit(1)

print(f"📊 Conectando em: {database_url[:60]}...")

try:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        # Versão do PostgreSQL
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✅ Conexão OK!")
        print(f"📦 PostgreSQL: {version[:70]}...")
        
        # Nome do banco
        result = conn.execute(text("SELECT current_database()"))
        db_name = result.fetchone()[0]
        print(f"🗄️  Banco: {db_name}")
        
        # Verificar ambiente
        if 'homolog' in db_name.lower():
            print("✅ Conectado no banco de HOMOLOGAÇÃO")
        elif 'go_mobi_db' == db_name.lower():
            print("⚠️  ATENÇÃO: Conectado no banco de PRODUÇÃO!")
        else:
            print(f"ℹ️  Banco: {db_name}")
            
        # Contar tabelas
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        table_count = result.fetchone()[0]
        print(f"📊 Tabelas no banco: {table_count}")
        
        # Verificar usuário conectado
        result = conn.execute(text("SELECT current_user"))
        user = result.fetchone()[0]
        print(f"👤 Usuário: {user}")
        
except Exception as e:
    print(f"❌ Erro de conexão: {e}")
    print("\n💡 Dicas:")
    print("  1. Verifique se o DATABASE_URL está correto no .env")
    print("  2. Verifique se o banco está ativo no Render")
    print("  3. Verifique sua conexão com a internet")