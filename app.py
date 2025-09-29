import click
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# --- 1. CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///doug_moving.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Use uma chave segura
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-forte-e-diferente'
db = SQLAlchemy(app)

# --- 2. CONFIGURAÇÃO DO FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Rota para redirecionar usuários não logados
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 3. MODELOS DO BANCO DE DADOS ---


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # 'solicitante' ou 'motorista'
    role = db.Column(db.String(20), nullable=False)


class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Disponível')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='motorista_profile', uselist=False)
    corridas = db.relationship('Corrida', backref='motorista', lazy=True)


class Corrida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(200), nullable=False)
    destino = db.Column(db.String(200), nullable=False)
    horario_busca = db.Column(db.DateTime, nullable=False)
    passageiros = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pendente')

    # --- NOVOS CAMPOS DE TIMESTAMP ---
    data_solicitacao = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow)
    # Pode ser nulo até o aceite
    data_aceite = db.Column(db.DateTime, nullable=True)
    # Pode ser nulo até a finalização
    data_finalizacao = db.Column(db.DateTime, nullable=True)

    solicitante_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    solicitante = db.relationship('User', backref='corridas_solicitadas')
    motorista_id = db.Column(
        db.Integer, db.ForeignKey('motorista.id'), nullable=True)


# --- 4. ROTAS DE AUTENTICAÇÃO ---


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            # A linha abaixo já faz o redirecionamento correto via 'home'
            return redirect(url_for('home'))
        else:
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email']
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado. Tente fazer o login.', 'warning')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(
            request.form['password'], method='pbkdf2:sha256')
        role = request.form['role']
        new_user = User(email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        if role == 'motorista':
            nome_motorista = email.split('@')[0].capitalize()
            novo_motorista = Motorista(
                nome=nome_motorista, user_id=new_user.id, status='Disponível')
            db.session.add(novo_motorista)
            db.session.commit()

        flash('Cadastro realizado com sucesso! Faça o login para continuar.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- 5. ROTAS PRINCIPAIS E DASHBOARDS ---


@app.route('/')
@login_required
def home():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))  # <<-- NOVA LINHA
    elif current_user.role == 'motorista':
        return redirect(url_for('dashboard_motorista'))
    else:
        return redirect(url_for('dashboard_solicitante'))


@app.route('/dashboard/solicitante', methods=['GET', 'POST'])
@login_required
def dashboard_solicitante():
    if current_user.role != 'solicitante':
        return redirect(url_for('home'))

    if request.method == 'POST':
        nova_corrida = Corrida(
            origem=request.form['origem'],
            destino=request.form['destino'],
            horario_busca=datetime.fromisoformat(
                request.form['horario_busca']),
            passageiros=int(request.form['passageiros']),
            solicitante_id=current_user.id
        )
        db.session.add(nova_corrida)
        db.session.commit()
        flash('Corrida solicitada com sucesso!', 'success')
        return redirect(url_for('dashboard_solicitante'))

    corridas_solicitadas = Corrida.query.filter_by(
        solicitante_id=current_user.id).order_by(Corrida.id.desc()).all()
    return render_template('dashboard_solicitante.html', corridas=corridas_solicitadas)


@app.route('/dashboard/motorista')
@login_required
def dashboard_motorista():
    if current_user.role != 'motorista':
        return redirect(url_for('home'))

    motorista = Motorista.query.filter_by(user_id=current_user.id).first()
    corridas_pendentes = Corrida.query.filter_by(status='Pendente').all()
    corrida_atual = Corrida.query.filter_by(
        motorista_id=motorista.id, status='Em Andamento').first()

    return render_template('dashboard_motorista.html', motorista=motorista, corridas_pendentes=corridas_pendentes, corrida_atual=corrida_atual)

# --- 6. AÇÕES DO MOTORISTA ---


@app.route('/motorista/pegar-corrida/<int:corrida_id>')
@login_required
def pegar_corrida(corrida_id):
    if current_user.role != 'motorista':
        return redirect(url_for('home'))

    motorista = Motorista.query.filter_by(user_id=current_user.id).first()
    if motorista.status != 'Disponível':
        flash('Você precisa finalizar sua corrida atual antes de pegar outra.', 'warning')
        return redirect(url_for('dashboard_motorista'))

    corrida = Corrida.query.get_or_404(corrida_id)
    if corrida.status == 'Pendente':
        corrida.motorista_id = motorista.id
        corrida.status = 'Em Andamento'
        motorista.status = 'Ocupado'
        corrida.data_aceite = datetime.utcnow()  # <-- ADICIONAR ESTA LINHA
        db.session.commit()

        flash(
            f'Você pegou a corrida de {corrida.origem} para {corrida.destino}.', 'success')
    else:
        flash('Esta corrida não está mais disponível.', 'warning')

    return redirect(url_for('dashboard_motorista'))


@app.route('/motorista/finalizar-corrida/<int:corrida_id>')
@login_required
def finalizar_corrida(corrida_id):
    if current_user.role != 'motorista':
        return redirect(url_for('home'))

    motorista = Motorista.query.filter_by(user_id=current_user.id).first()
    corrida = Corrida.query.get_or_404(corrida_id)

    if corrida.motorista_id == motorista.id and corrida.status == 'Em Andamento':
        corrida.status = 'Finalizada'
        motorista.status = 'Disponível'
        corrida.data_finalizacao = datetime.utcnow()  # <-- ADICIONAR ESTA LINHA
        db.session.commit()

        flash('Corrida finalizada com sucesso! Você está disponível novamente.', 'success')
    else:
        flash('Ação inválida ou a corrida não pertence a você.', 'danger')

    return redirect(url_for('dashboard_motorista'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # --- LÓGICA DE FILTRO ---
    status_filtro = request.args.get('status', default=None, type=str)

    query_corridas = Corrida.query  # Começa com a query base

    if status_filtro and status_filtro != 'todos':
        query_corridas = query_corridas.filter(Corrida.status == status_filtro)

    todas_as_corridas = query_corridas.order_by(Corrida.id.desc()).all()
    # --- FIM DA LÓGICA DE FILTRO ---

    todos_os_motoristas = Motorista.query.all()

    return render_template('admin_dashboard.html',
                           motoristas=todos_os_motoristas,
                           corridas=todas_as_corridas,
                           status_atual=status_filtro)  # Passa o filtro atual para o template


# --- 8. COMANDOS DE ADMINISTRAÇÃO ---


@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email, password):
    """Cria um novo usuário administrador."""
    # Verifica se o app está no contexto correto para acessar o db
    with app.app_context():
        if User.query.filter_by(email=email).first():
            print(f"Erro: O email '{email}' já existe.")
            return

        hashed_password = generate_password_hash(
            password, method='pbkdf2:sha256')
        admin_user = User(email=email, password=hashed_password, role='admin')
        db.session.add(admin_user)
        db.session.commit()
        print(f"Administrador '{email}' criado com sucesso!")






# --- 7. INICIALIZAÇÃO ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Cria as tabelas se não existirem
    app.run(debug=True, port=5000)
