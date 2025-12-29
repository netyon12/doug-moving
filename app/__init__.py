# app/__init__.py
import os
from flask import Flask, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user, logout_user
from flask_caching import Cache
from dotenv import load_dotenv
from app.logging_config import setup_logging

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

    # ✅ ADICIONAR: Configurar logging
    setup_logging(app)

    # --- INICIALIZAÇÃO DAS EXTENSÕES ---
    db.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)
    migrate = Migrate(app, db)
    
    # --- INICIALIZAÇÃO DO MIDDLEWARE MULTI-TENANT ---
    from .config.db_middleware import init_multitenant_middleware
    init_multitenant_middleware(app)

    # Configuração do Flask-Login
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        from flask import session
        from .config.tenant_utils import query_tenant
        
        # Buscar empresa ativa da sessão
        empresa_slug = session.get('empresa_ativa_slug')
        
        # Se não há empresa ativa, buscar no Banco 1 (padrão)
        if not empresa_slug:
            return User.query.get(int(user_id))
        
        # Com empresa ativa, buscar no banco da empresa (tenant)
        # Isso funciona para TODOS os roles, incluindo motoristas replicados
        user = query_tenant(User).get(int(user_id))
        
        if not user:
            # Fallback: buscar no Banco 1 (para compatibilidade)
            print(f"[LOAD_USER] User {user_id} não encontrado no banco de {empresa_slug}, buscando no Banco 1...")
            return User.query.get(int(user_id))
        
        return user

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

    # NOVO: Consulta de Viagens
    from .blueprints.consulta_viagens import consulta_bp
    app.register_blueprint(consulta_bp)

    # NOVO: Cadastro de Usuários (Configurações)
    from .blueprints.usuarios.cad_users import cad_users_bp
    app.register_blueprint(cad_users_bp)

    # NOVO: Blueprint do Operador
    from .blueprints.operador import operador_bp
    app.register_blueprint(operador_bp)

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
        if not current_user.is_authenticated:
            # Embora tenha @login_required, esta é uma verificação de segurança
            return redirect(url_for('auth.login'))

        if current_user.role == 'admin':
            # Redireciona para a função 'dashboard' dentro do blueprint 'admin'
            return redirect(url_for('admin.admin_dashboard'))

        elif current_user.role == 'gerente':
            return redirect(url_for('gerente.dashboard_gerente'))

        elif current_user.role == 'supervisor':
            # Redireciona para a função 'dashboard' dentro do blueprint 'supervisor'
            return redirect(url_for('supervisor.dashboard_supervisor'))

        elif current_user.role == 'motorista':
            return redirect(url_for('motorista.dashboard_motorista'))

        elif current_user.role == 'operador':
            return redirect(url_for('operador.operador_dashboard'))

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
        SECRET_KEY = os.getenv('SECRET_KEY')
        if not SECRET_KEY:
            import secrets
            SECRET_KEY = secrets.token_hex(32)
            print("\n" + "="*70)
            print("⚠️  WARNING: SECRET_KEY não encontrada no arquivo .env!")
            print("   Gerando chave temporária para esta sessão.")
            print("   Para produção, adicione ao .env:")
            print(f"   SECRET_KEY={SECRET_KEY}")
            print("="*70 + "\n")
        elif len(SECRET_KEY) < 32:
            print("\n" + "="*70)
            print("⚠️  WARNING: SECRET_KEY muito curta (mínimo 32 caracteres)!")
            print("   Use: python -c 'import secrets; print(secrets.token_hex(32))'")
            print("="*70 + "\n")

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

    # ===== NOVO: Context Processor para Ambiente =====

    @app.context_processor
    def inject_ambiente():
        """Injeta informação do ambiente (homologacao/producao) em todos os templates."""
        ambiente = os.getenv('AMBIENTE', 'producao')
        return {'ambiente': ambiente}

    # ===== NOVO: Context Processor para Multi-Tenant =====

    @app.context_processor
    def inject_multitenant_info():
        """Injeta informações multi-tenant em todos os templates."""
        from flask import session
        from flask_login import current_user
        
        multitenant_info = {
            'empresa_ativa_nome': session.get('empresa_ativa_nome', ''),
            'empresa_ativa_slug': session.get('empresa_ativa_slug', ''),
            'empresa_ativa_id': session.get('empresa_ativa_id'),
            'is_banco_local': session.get('is_banco_local', True),
            'pode_trocar_empresa': False,
            'empresas_disponiveis': []
        }
        
        # Verificar se pode trocar de empresa
        if current_user.is_authenticated:
            if current_user.role in ['admin', 'operador']:
                multitenant_info['pode_trocar_empresa'] = True
            elif current_user.role == 'motorista' and hasattr(current_user, 'motorista') and current_user.motorista:
                empresas_lista = current_user.motorista.get_empresas_lista() if hasattr(current_user.motorista, 'get_empresas_lista') else []
                multitenant_info['pode_trocar_empresa'] = len(empresas_lista) > 1
        
        return multitenant_info

    return app
