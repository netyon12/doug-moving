# run.py
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
import click
from sqlalchemy import text
from flask_migrate import Migrate

# Cria a aplicação usando a nossa factory
app = create_app()
migrate = Migrate(app, db)  # ← ADICIONE ESTA LINHA

# =============================================================================
# COMANDOS DE LINHA DE COMANDO (CLI)
# =============================================================================

@app.cli.command('db-drop')
def db_drop():
    """Apaga todas as tabelas do banco de dados (modo PostgreSQL)."""
    # Comando específico para PostgreSQL para forçar a exclusão em cascata
    db.session.execute(text('DROP SCHEMA public CASCADE;'))
    db.session.execute(text('CREATE SCHEMA public;'))
    db.session.commit()
    print('Banco de dados (schema) reiniciado com sucesso.')



### CRIAÇÃO DO USUÁRIO ADMIN NO BANCO

@app.cli.command('db-create')
def db_create():
    """Cria todas as tabelas do banco de dados a partir dos modelos."""
    db.create_all()
    print('Banco de dados criado com sucesso.')
    
    # Bloco que cria o admin inicial automaticamente
    with app.app_context():
        if not User.query.filter_by(role='admin').first():
            print("Nenhum admin encontrado, criando um novo...")
            hashed_password = generate_password_hash('admin', method='pbkdf2:sha256')
            admin_user = User(email='admin@netyonsolutions.com', password=hashed_password, role='admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Admin 'admin@netyonsolutions.com' criado com sucesso!")






# =============================================================================
# EXECUÇÃO DA APLICAÇÃO
# =============================================================================

if __name__ == '__main__':
    app.run(debug=True)
