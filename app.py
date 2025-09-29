import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import click
import csv
from io import StringIO
from flask import Response
from flask_migrate import Migrate

######################################### --- 1. CONFIGURAÇÃO INICIAL (sem alterações) ---


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///doug_moving.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-forte-e-diferente'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- 2. CONFIGURAÇÃO DO FLASK-LOGIN (sem alterações) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




################################################## --- 3. NOVOS MODELOS DO BANCO DE DADOS ---

# O modelo User agora é a base para login, com 'role' diferenciando os perfis.
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'supervisor', 'motorista'
    supervisor_profile = db.relationship('Supervisor', back_populates='user', uselist=False)
    motorista_profile = db.relationship('Motorista', back_populates='user', uselist=False)

# NOVO MODELO: Supervisor (antigo Solicitante) com campos detalhados.
class Supervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100), nullable=False)
    endereco = db.Column(db.String(200))
    telefone = db.Column(db.String(20))
    observacoes = db.Column(db.Text)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='supervisor_profile')

# MODELO ATUALIZADO: Motorista com novos campos.
class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    bloco_origem = db.Column(db.String(50))
    status = db.Column(db.String(20), nullable=False, default='Disponível')
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='motorista_profile')
    corridas = db.relationship('Corrida', backref='motorista', lazy=True)

# NOVO MODELO: Funcionário, que não tem login, mas pertence a uma empresa.
class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    bloco_origem = db.Column(db.String(50))

# MODELO ATUALIZADO: Corrida, agora ligada a um Funcionário.
class Corrida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(200), nullable=False)
    destino = db.Column(db.String(200), nullable=False)
    horario_busca = db.Column(db.DateTime, nullable=False)
    passageiros = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pendente')
    
    data_solicitacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_aceite = db.Column(db.DateTime, nullable=True)
    data_finalizacao = db.Column(db.DateTime, nullable=True)
    
    # A corrida agora é solicitada por um Supervisor (através do seu User)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    solicitante = db.relationship('User', backref='corridas_solicitadas')
    
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=True)
    
    # Novo campo para identificar o funcionário transportado
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)
    funcionario = db.relationship('Funcionario', backref='corridas')


# NOVO MODELO PARA AUDITORIA DE CANCELAMENTOS
class LogCancelamentoMotorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    corrida_id = db.Column(db.Integer, db.ForeignKey('corrida.id'), nullable=False)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    
    corrida = db.relationship('Corrida', backref='cancelamentos_log')
    motorista = db.relationship('Motorista', backref='cancelamentos_log')



################################# --- 4. ROTAS DE AUTENTICAÇÃO (Login e Logout permanecem, Register será removida) ---

@app.route('/login', methods=['GET', 'POST'])
def login():

    # --- BLOCO TEMPORÁRIO PARA CRIAR O ADMIN ---
    # Verifica se já existe algum usuário com a role 'admin'
    if not User.query.filter_by(role='admin').first():
        print("Nenhum admin encontrado, criando um novo...")
        # Criptografa a senha que você quer usar
        hashed_password = generate_password_hash('admin', method='pbkdf2:sha256')
        # Cria o novo usuário admin
        admin_user = User(email='admin@netyonsolutions.com', password=hashed_password, role='admin')
        # Adiciona ao banco de dados
        db.session.add(admin_user)
        db.session.commit()
        print("Admin 'admin@netyonsolutions.com' criado com sucesso!")
    # --- FIM DO BLOCO TEMPORÁRIO ---


    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
    return render_template('login.html')



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


######################################### --- 5. ROTAS PRINCIPAIS E DASHBOARDS (Serão reescritas) ---

@app.route('/')
@login_required
def home():
    # A lógica de redirecionamento será ajustada para os novos perfis
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'supervisor':
        return redirect(url_for('dashboard_supervisor')) # Novo nome
    elif current_user.role == 'motorista':
        return redirect(url_for('dashboard_motorista'))
    else:
        return "<h1>Perfil de usuário desconhecido.</h1>"


# A rota do admin será o nosso foco principal para adicionar os cadastros
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    aba_ativa = request.args.get('aba', 'corridas')
    
    # Lógica de Filtro para Corridas
    data_inicio_str = request.args.get('data_inicio', '')
    data_fim_str = request.args.get('data_fim', '')
    
    corridas_query = Corrida.query
    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        corridas_query = corridas_query.filter(Corrida.data_solicitacao >= data_inicio)
    if data_fim_str:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        corridas_query = corridas_query.filter(Corrida.data_solicitacao <= data_fim)

    dados = {
        'motoristas': Motorista.query.order_by(Motorista.nome).all(),
        'supervisores': Supervisor.query.order_by(Supervisor.nome).all(),
        'funcionarios': Funcionario.query.order_by(Funcionario.nome).all(),
        'corridas': corridas_query.order_by(Corrida.id.desc()).all()
    }
    
    return render_template('admin_dashboard.html', 
                           dados=dados,
                           aba_ativa=aba_ativa,
                           data_inicio=data_inicio_str, # Passa os filtros para o template
                           data_fim=data_fim_str)




# --- 6. ROTAS DE CADASTRO PELO ADMIN ---

@app.route('/admin/cadastrar_motorista', methods=['GET', 'POST'])
@login_required
def cadastrar_motorista():
    # 1. Garante que apenas o admin acesse esta página
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # 2. Se o formulário for enviado (método POST)
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Verifica se o email já existe na tabela User
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado. Tente outro.', 'warning')
            return redirect(url_for('cadastrar_motorista'))

        # Cria o registro na tabela User para o login
        hashed_password = generate_password_hash(request.form.get('senha'), method='pbkdf2:sha256')
        new_user = User(
            email=email,
            password=hashed_password,
            role='motorista'
        )
        db.session.add(new_user)
        db.session.commit() # Commit para que o new_user.id seja gerado

        # Cria o registro na tabela Motorista com os detalhes
        novo_motorista = Motorista(
            nome=request.form.get('nome'),
            telefone=request.form.get('telefone'),
            endereco=request.form.get('endereco'),
            bloco_origem=request.form.get('bloco_origem'),
            user_id=new_user.id  # Associa o motorista ao usuário recém-criado
        )
        db.session.add(novo_motorista)
        db.session.commit()

        flash(f'Motorista {novo_motorista.nome} cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))

    # 3. Se for um acesso normal (método GET), apenas mostra a página com o formulário
    return render_template('cadastrar_motorista.html')



@app.route('/admin/cadastrar_supervisor', methods=['GET', 'POST'])
@login_required
def cadastrar_supervisor():
    # 1. Garante que apenas o admin acesse
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # 2. Se o formulário for enviado (método POST)
    if request.method == 'POST':
        email = request.form.get('email')
        
        # Verifica se o email já existe
        if User.query.filter_by(email=email).first():
            flash('Este email já está cadastrado. Tente outro.', 'warning')
            return redirect(url_for('cadastrar_supervisor'))

        # Cria o registro na tabela User para o login
        hashed_password = generate_password_hash(request.form.get('senha'), method='pbkdf2:sha256')
        new_user = User(
            email=email,
            password=hashed_password,
            role='supervisor'
        )
        db.session.add(new_user)
        db.session.commit()

        # Cria o registro na tabela Supervisor com os detalhes
        novo_supervisor = Supervisor(
            nome=request.form.get('nome'),
            empresa=request.form.get('empresa'),
            endereco=request.form.get('endereco'),
            telefone=request.form.get('telefone'),
            observacoes=request.form.get('observacoes'),
            user_id=new_user.id
        )
        db.session.add(novo_supervisor)
        db.session.commit()

        flash(f'Supervisor {novo_supervisor.nome} cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))

    # 3. Se for um acesso GET, apenas mostra a página com o formulário
    return render_template('cadastrar_supervisor.html')



@app.route('/admin/cadastrar_funcionario', methods=['GET', 'POST'])
@login_required
def cadastrar_funcionario():
    # 1. Garante que apenas o admin acesse
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # 2. Se o formulário for enviado (método POST)
    if request.method == 'POST':
        # Como não há login, não precisamos verificar email duplicado ou criar User.
        # Apenas criamos o registro do funcionário.
        novo_funcionario = Funcionario(
            nome=request.form.get('nome'),
            empresa=request.form.get('empresa'),
            email=request.form.get('email'),
            telefone=request.form.get('telefone'),
            endereco=request.form.get('endereco'),
            bloco_origem=request.form.get('bloco_origem')
        )
        db.session.add(novo_funcionario)
        db.session.commit()

        flash(f'Funcionário {novo_funcionario.nome} cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))

    # 3. Se for um acesso GET, apenas mostra a página com o formulário
    return render_template('cadastrar_funcionario.html')


@app.route('/dashboard/supervisor', methods=['GET', 'POST'])
@login_required
def dashboard_supervisor():
    # 1. Garante que apenas supervisores acessem
    if current_user.role != 'supervisor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # Busca o perfil detalhado do supervisor logado
    supervisor_profile = current_user.supervisor_profile 
    funcionarios_da_empresa = Funcionario.query.filter_by(empresa=supervisor_profile.empresa).all()

    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado.', 'danger')
        return redirect(url_for('logout'))

    # 2. Se o formulário for enviado (método POST)
    if request.method == 'POST':
        nova_corrida = Corrida(
            origem=request.form.get('origem'),
            destino=request.form.get('destino'),
            horario_busca=datetime.fromisoformat(request.form.get('horario_busca')),
            passageiros=int(request.form.get('passageiros')),
            funcionario_id=request.form.get('funcionario_id'), # Pega o ID do funcionário selecionado
            solicitante_id=current_user.id # O solicitante é o supervisor logado
        )
        db.session.add(nova_corrida)
        db.session.commit()
        flash('Corrida solicitada com sucesso!', 'success')
        return redirect(url_for('dashboard_supervisor'))

    # 3. Se for um acesso normal (método GET)
    
    # Busca os funcionários que pertencem à mesma empresa do supervisor
    funcionarios_da_empresa = Funcionario.query.filter_by(empresa=supervisor_profile.empresa).all()
    
    # Busca o histórico de corridas solicitadas por este supervisor
    corridas_solicitadas = Corrida.query.filter_by(solicitante_id=current_user.id).order_by(Corrida.id.desc()).all()

    # Renderiza o template, passando a lista de funcionários e o histórico de corridas
    return render_template('dashboard_supervisor.html', 
                           corridas=corridas_solicitadas, 
                           funcionarios=funcionarios_da_empresa)





@app.route('/dashboard/motorista')
@login_required
def dashboard_motorista():
    # 1. Garante que apenas motoristas acessem
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # Busca o perfil detalhado do motorista logado
    motorista_profile = current_user.motorista_profile
    if not motorista_profile:
        flash('Perfil de motorista não encontrado.', 'danger')
        return redirect(url_for('logout'))

    # 2. Busca os dados para exibir no painel
    # Corridas com status 'Pendente' que ainda não têm motorista
    corridas_pendentes = Corrida.query.filter_by(status='Pendente', motorista_id=None).all()
    
    # A corrida que este motorista específico está fazendo no momento
    corrida_atual = Corrida.query.filter_by(
        motorista_id=motorista_profile.id, 
        status='Em Andamento'
    ).first()

    # 3. Renderiza o template, passando os dados
    return render_template('dashboard_motorista.html', 
                           motorista=motorista_profile, 
                           corridas_pendentes=corridas_pendentes, 
                           corrida_atual=corrida_atual)





# --- 7. AÇÕES DO MOTORISTA ---

@app.route('/motorista/pegar-corrida/<int:corrida_id>')
@login_required
def pegar_corrida(corrida_id):
    if current_user.role != 'motorista':
        return redirect(url_for('home'))

    motorista = current_user.motorista_profile
    if motorista.status != 'Disponível':
        flash('Você precisa finalizar sua corrida atual antes de pegar outra.', 'warning')
        return redirect(url_for('dashboard_motorista'))

    corrida = Corrida.query.get_or_404(corrida_id)
    if corrida.status == 'Pendente':
        corrida.motorista_id = motorista.id
        corrida.status = 'Em Andamento'
        corrida.data_aceite = datetime.utcnow() # Registra o momento do aceite
        motorista.status = 'Ocupado'
        db.session.commit()
        flash(f'Você pegou a corrida para o funcionário {corrida.funcionario.nome}.', 'success')
    else:
        flash('Esta corrida não está mais disponível.', 'warning')

    return redirect(url_for('dashboard_motorista'))


@app.route('/motorista/finalizar-corrida/<int:corrida_id>')
@login_required
def finalizar_corrida(corrida_id):
    if current_user.role != 'motorista':
        return redirect(url_for('home'))

    motorista = current_user.motorista_profile
    corrida = Corrida.query.get_or_404(corrida_id)

    if corrida.motorista_id == motorista.id and corrida.status == 'Em Andamento':
        corrida.status = 'Finalizada'
        corrida.data_finalizacao = datetime.utcnow() # Registra o momento da finalização
        motorista.status = 'Disponível'
        db.session.commit()
        flash('Corrida finalizada com sucesso! Você está disponível novamente.', 'success')
    else:
        flash('Ação inválida ou a corrida não pertence a você.', 'danger')

    return redirect(url_for('dashboard_motorista'))


@app.route('/supervisor/cancelar-corrida/<int:corrida_id>')
@login_required
def cancelar_corrida_supervisor(corrida_id):
    if current_user.role != 'supervisor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    corrida = Corrida.query.get_or_404(corrida_id)

    # Garante que o supervisor só pode cancelar suas próprias corridas e que estejam pendentes
    if corrida.solicitante_id != current_user.id:
        flash('Você não tem permissão para cancelar esta corrida.', 'danger')
        return redirect(url_for('dashboard_supervisor'))

    if corrida.status != 'Pendente':
        flash('Esta corrida não pode mais ser cancelada, pois já foi aceita por um motorista.', 'warning')
        return redirect(url_for('dashboard_supervisor'))

    corrida.status = 'Cancelado'
    db.session.commit()
    flash('A solicitação de corrida foi cancelada.', 'success')
    return redirect(url_for('dashboard_supervisor'))




@app.route('/motorista/cancelar-aceite/<int:corrida_id>')
@login_required
def cancelar_aceite_motorista(corrida_id):
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    corrida = Corrida.query.get_or_404(corrida_id)
    motorista = current_user.motorista_profile

    # Garante que o motorista só pode cancelar a corrida que é dele e está em andamento
    if corrida.motorista_id != motorista.id or corrida.status != 'Em Andamento':
        flash('Ação inválida.', 'danger')
        return redirect(url_for('dashboard_motorista'))

    # Cria o log de auditoria
    novo_log = LogCancelamentoMotorista(
        corrida_id=corrida.id,
        motorista_id=motorista.id
    )
    db.session.add(novo_log)

    # Reseta o status da corrida e do motorista
    corrida.status = 'Pendente'
    corrida.motorista_id = None # Desvincula o motorista da corrida
    corrida.data_aceite = None # Limpa a data de aceite
    motorista.status = 'Disponível'
    
    db.session.commit()
    flash('O aceite da corrida foi cancelado. A corrida está disponível para outros motoristas.', 'success')
    return redirect(url_for('dashboard_motorista'))




########################3 Rota para a exportação do CSV
@app.route('/admin/exportar_corridas_csv')
@login_required
def exportar_corridas_csv():
    if current_user.role != 'admin':
        return redirect(url_for('home'))

    # Pega os mesmos filtros da URL que usamos no dashboard
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    query = Corrida.query

    # Aplica os filtros de data se eles existirem
    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        query = query.filter(Corrida.data_solicitacao >= data_inicio)
    if data_fim_str:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Corrida.data_solicitacao <= data_fim)

    corridas_filtradas = query.order_by(Corrida.id.desc()).all()

    
    
    
    ######################### Lógica para gerar o CSV
    def generate():
        data = StringIO()
        writer = csv.writer(data)

        # Escreve o cabeçalho
        writer.writerow(('ID', 'Funcionario', 'Empresa', 'Origem', 'Destino', 'Status', 'Motorista', 'Data Solicitacao', 'Data Aceite', 'Data Finalizacao'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        # Escreve as linhas de dados
        for corrida in corridas_filtradas:
            writer.writerow((
                corrida.id,
                corrida.funcionario.nome if corrida.funcionario else '',
                corrida.funcionario.empresa if corrida.funcionario else '',
                corrida.origem,
                corrida.destino,
                corrida.status,
                corrida.motorista.nome if corrida.motorista else '',
                corrida.data_solicitacao.strftime('%Y-%m-%d %H:%M:%S') if corrida.data_solicitacao else '',
                corrida.data_aceite.strftime('%Y-%m-%d %H:%M:%S') if corrida.data_aceite else '',
                corrida.data_finalizacao.strftime('%Y-%m-%d %H:%M:%S') if corrida.data_finalizacao else ''
            ))
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    # Cria a resposta para o navegador forçar o download
    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="corridas.csv")
    return response



## Rota para Editar o perfil, podendo alterar o login e senha (chamando o editar_perfil.html)

# No seu app.py, substitua a rota editar_perfil pela versão abaixo

@app.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    if request.method == 'POST':
        action = request.form.get('action')

        # --- LÓGICA PARA ATUALIZAR O E-MAIL ---
        if action == 'update_profile':
            novo_email = request.form.get('email')
            password_check = request.form.get('password_check')

            if not password_check:
                flash('Você precisa informar sua senha atual para alterar o e-mail.', 'warning')
                return redirect(url_for('editar_perfil'))

            if not check_password_hash(current_user.password, password_check):
                flash('Senha incorreta. Não foi possível alterar o e-mail.', 'danger')
                return redirect(url_for('editar_perfil'))

            if novo_email != current_user.email:
                existing_user = User.query.filter_by(email=novo_email).first()
                if existing_user:
                    flash('Este e-mail já está em uso por outra conta.', 'warning')
                    return redirect(url_for('editar_perfil'))
            
            current_user.email = novo_email
            db.session.commit()
            flash('Seu e-mail foi atualizado com sucesso!', 'success')
            return redirect(url_for('editar_perfil'))

        # --- LÓGICA PARA ATUALIZAR A SENHA ---
        elif action == 'update_password':
            senha_atual = request.form.get('senha_atual')
            nova_senha = request.form.get('nova_senha')
            
            # Se o campo senha_atual estiver vazio, o usuário não quer alterar a senha.
            if not senha_atual:
                flash('Nenhuma alteração de senha foi feita.', 'info')
                return redirect(url_for('editar_perfil'))

            confirmar_senha = request.form.get('confirmar_senha')
            if not nova_senha or not confirmar_senha:
                flash('Para alterar a senha, preencha os campos de nova senha e confirmação.', 'warning')
                return redirect(url_for('editar_perfil'))

            if not check_password_hash(current_user.password, senha_atual):
                flash('A senha atual está incorreta.', 'danger')
                return redirect(url_for('editar_perfil'))

            if nova_senha != confirmar_senha:
                flash('A nova senha e a confirmação não correspondem.', 'danger')
                return redirect(url_for('editar_perfil'))

            current_user.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            db.session.commit()
            flash('Sua senha foi alterada com sucesso!', 'success')
            return redirect(url_for('editar_perfil'))

    return render_template('editar_perfil.html')










#################################################### --- 8. COMANDOS DE ADMINISTRAÇÃO (sem alterações) ---
@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
def create_admin(email, password):
    """Cria um novo usuário administrador."""
    with app.app_context():
        if User.query.filter_by(email=email).first():
            print(f"Erro: O email '{email}' já existe.")
            return
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        admin_user = User(email=email, password=hashed_password, role='admin')
        db.session.add(admin_user)
        db.session.commit()
        print(f"Administrador '{email}' criado com sucesso!")





## Para funcionar precisa fazer isso:
## Confirme rapidamente em Settings > Build & Deploy no Render que o comando ainda é:
## pip install -r requirements.txt && flask db-drop && flask db-create

# --- NOVOS COMANDOS PARA GERENCIAR O BANCO DE DADOS ---
@app.cli.command('db-drop')
def db_drop():
    """Apaga todas as tabelas do banco de dados."""
    db.drop_all()
    print('Banco de dados apagado com sucesso.')

@app.cli.command('db-create')
def db_create():
    """Cria todas as tabelas do banco de dados a partir dos modelos."""
    db.create_all()
    print('Banco de dados criado com sucesso.')










######################################################### --- 9. INICIALIZAÇÃO ---
if __name__ == '__main__':
    with app.app_context():
        # Este comando irá criar as novas tabelas no seu banco de dados local
        db.create_all()
    app.run(debug=True, port=5000)

