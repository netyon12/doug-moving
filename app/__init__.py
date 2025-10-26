# app/__init__.py
import os
from flask import Flask, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user, logout_user
from flask_caching import Cache
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Instâncias das extensões
db = SQLAlchemy()
login_manager = LoginManager()
cache = Cache()


def create_scoped_session():
    """
    Cria uma sessão isolada do SQLAlchemy para uso em threads.

    Esta função é usada quando precisamos acessar o banco de dados
    em threads background (como notificações assíncronas).

    Returns:
        scoped_session: Sessão isolada do SQLAlchemy
    """
    from sqlalchemy.orm import scoped_session, sessionmaker

    # Cria uma nova sessão usando o engine existente
    session_factory = sessionmaker(bind=db.engine)
    Session = scoped_session(session_factory)

    return Session


def create_app():
    """Cria e configura a instância da aplicação Flask."""
    app = Flask(__name__)

    # --- CONFIGURAÇÕES DA APLICAÇÃO ---
    # Carrega as configurações (SECRET_KEY, DATABASE_URL, etc.)
    # Exemplo: app.config.from_object('config.Config')
    app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-forte-e-diferente'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 'sqlite:///doug_moving.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Para não mostrar as queries SQL no terminal.
    app.config['SQLALCHEMY_ECHO'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(
        os.path.dirname(__file__)), 'static/profile_pics')

    # Configuração do Flask-Caching
    app.config['CACHE_TYPE'] = 'SimpleCache'  # Cache em memória
    app.config['CACHE_DEFAULT_TIMEOUT'] = 3600  # 1 hora

    # --- INICIALIZAÇÃO DAS EXTENSÕES ---
    db.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)
    migrate = Migrate(app, db)

    # Configuração do Flask-Login
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Aponta para a rota 'login' dentro do blueprint 'auth'
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, faça o login para acessar esta página."
    login_manager.login_message_category = "info"

    # --- REGISTRO DOS BLUEPRINTS ---
    # Importa e registra cada blueprint da sua nova estrutura
    from .blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Importa o blueprint admin (já carrega todos os módulos automaticamente)
    from .blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)

    from .blueprints.gerente import gerente_bp
    app.register_blueprint(gerente_bp)

    from .blueprints.supervisor import supervisor_bp
    app.register_blueprint(supervisor_bp)

    from .blueprints.motorista import motorista_bp
    app.register_blueprint(motorista_bp)

    from .blueprints.admin_audit_routes import audit_bp
    app.register_blueprint(audit_bp)

    from .blueprints.relatorios import relatorios_bp
    app.register_blueprint(relatorios_bp)

    from .blueprints.financeiro import financeiro_bp
    app.register_blueprint(financeiro_bp)

    # --- FILTROS PERSONALIZADOS DO JINJA2 ---

    @app.template_filter('number_format')
    def number_format_filter(value):
        """Formata números com separador de milhares."""
        try:
            return "{:,}".format(int(value)).replace(',', '.')
        except (ValueError, TypeError):
            return value

    # --- ROTA PWA OFFLINE ---

    @app.route('/offline')
    def offline():
        """Página exibida quando o usuário está offline."""
        from flask import render_template
        return render_template('offline.html')

    # --- ROTA INSTRUÇÕES DE INSTALAÇÃO PWA ---
    @app.route('/instalar')
    def instalar():
        """Página com instruções para instalar o PWA no smartphone."""
        from flask import render_template
        return render_template('instalar.html')

    # --- ROTA PRINCIPAL (PORTA DE ENTRADA) ---
    @app.route('/')
    @login_required
    def home():
        """
        Rota principal que redireciona o usuário logado para o dashboard correto.
        """
        if current_user.role == 'admin':
            # Redireciona para a função 'dashboard' dentro do blueprint 'admin'
            return redirect(url_for('admin.admin_dashboard'))

        elif current_user.role == 'gerente':
            return redirect(url_for('gerente.dashboard_gerente'))

        elif current_user.role == 'supervisor':
            # Redireciona para a função 'dashboard' dentro do blueprint 'supervisor'
            return redirect(url_for('supervisor.dashboard_supervisor'))

        elif current_user.role == 'motorista':
            # Redireciona para a função 'dashboard' dentro do blueprint 'motorista'
            return redirect(url_for('motorista.dashboard_motorista'))

        else:
            # Caso de segurança: se a role for desconhecida, desloga o usuário.
            flash('Perfil de usuário inválido. Por favor, contate o suporte.', 'danger')
            logout_user()
            return redirect(url_for('auth.login'))

    # Carrega variáveis de ambiente
    load_dotenv()

    class Config:
        # Banco de dados (lê de variável de ambiente)
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
        SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Outras configs
        SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
        FLASK_ENV = os.getenv('FLASK_ENV', 'production')
        DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'

    # ===== NOVO: Context Processor para Timeout =====

    @app.context_processor
    def inject_timeout_config():
        """Injeta configuração de timeout em todos os templates."""
        from .models import Configuracao
        config_timeout = Configuracao.query.filter_by(
            chave='timeout_inatividade_minutos'
        ).first()
        timeout = int(config_timeout.valor) if config_timeout else 30
        return {'timeout_config': timeout}

    return app
