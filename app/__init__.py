# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
#from flask_migrate import Migrate  ##Depois tira o comentário
from flask_login import LoginManager

# Inicializa as extensões (ainda sem app associado)
db = SQLAlchemy()
## migrate = Migrate()  ## Depois tira o comentario
login_manager = LoginManager()
login_manager.login_view = 'routes.login' # 'routes' é o nome do blueprint
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"

def create_app():
    """Cria e configura uma instância da aplicação Flask."""
    app = Flask(__name__)
    
    # Configurações da aplicação
    app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-forte-e-diferente'
    # A linha abaixo garante que o Render use o banco de dados de produção
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///../doug_moving.db').replace("postgres://", "postgresql://")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Associa as extensões à instância da aplicação
    db.init_app(app)
    #migrate.init_app(app, db) ## depois tira o comentario
    login_manager.init_app(app)

    # Importa os modelos para que o Flask-Migrate os reconheça
    from . import models

    # Registra o Blueprint que contém as rotas
    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # Define a função para carregar o usuário
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    return app
