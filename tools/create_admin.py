# Arquivo dummy para evitar erro de build no Render
# O código de criação de admin foi movido para run.py
from werkzeug.security import generate_password_hash
from app.models import User
from app import create_app, db
print("Arquivo create_admin.py executado (dummy).")


app = create_app()

with app.app_context():
    # Verificar se já existe admin
    admin_existente = User.query.filter_by(
        email='admin@netyonsolutions.com').first()

    if admin_existente:
        print("❌ Usuário admin já existe!")
        print(f"   Email: {admin_existente.email}")
    else:
        # Criar novo admin usando os campos corretos do banco
        admin = User(
            email='admin@netyonsolutions.com',
            password=generate_password_hash('admin'),
            role='admin'
        )

        # Adicionar ao banco
        db.session.add(admin)
        db.session.commit()

        print("✅ Usuário admin criado com sucesso!")
        print(f"   Email: admin@netyonsolutions.com")
        print(f"   Senha: admin")
        print(f"   ⚠️  MUDE A SENHA APÓS O PRIMEIRO LOGIN!")
