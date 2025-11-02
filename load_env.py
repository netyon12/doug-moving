# load_env.py
from dotenv import load_dotenv
import os

# Carrega .env.local se existir, senão carrega .env
env_file = '.env.local' if os.path.exists('.env.local') else '.env'
load_dotenv(env_file)

print(f"✅ Variáveis carregadas de: {env_file}")
print(f"📊 DATABASE_URL: {os.getenv('DATABASE_URL', 'NÃO CONFIGURADO')[:50]}...")