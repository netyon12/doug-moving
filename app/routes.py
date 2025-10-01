# app/routes.py (VERSÃO CORRIGIDA)
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

from . import db
from .models import User, Supervisor, Colaborador, Motorista, Bloco, Viagem, Solicitacao
from io import StringIO
import csv

bp = Blueprint('routes', __name__)

# =============================================================================
# ROTAS DE AUTENTICAÇÃO E NAVEGAÇÃO PRINCIPAL
# =============================================================================

@bp.route('/')
@login_required
def home():
    if current_user.role == 'admin':
        return redirect(url_for('routes.admin_dashboard'))
    elif current_user.role == 'supervisor':
        return redirect(url_for('routes.dashboard_supervisor'))
    elif current_user.role == 'motorista':
        return redirect(url_for('routes.dashboard_motorista'))
    else:
        flash('Perfil de usuário desconhecido.', 'danger')
        return redirect(url_for('routes.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('routes.home'))
        else:
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
            
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('routes.login'))

@bp.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            novo_email = request.form.get('email')
            password_check = request.form.get('password_check')

            if not password_check or not check_password_hash(current_user.password, password_check):
                flash('Senha atual incorreta.', 'danger')
                return redirect(url_for('routes.editar_perfil'))

            if novo_email != current_user.email and User.query.filter_by(email=novo_email).first():
                flash('Este e-mail já está em uso por outra conta.', 'warning')
                return redirect(url_for('routes.editar_perfil'))
            
            current_user.email = novo_email
            db.session.commit()
            flash('Seu e-mail foi atualizado com sucesso!', 'success')
            return redirect(url_for('routes.editar_perfil'))

        elif action == 'update_password':
            senha_atual = request.form.get('senha_atual')
            nova_senha = request.form.get('nova_senha')
            confirmar_senha = request.form.get('confirmar_senha')

            if not senha_atual:
                flash('Nenhuma alteração de senha foi feita.', 'info')
                return redirect(url_for('routes.editar_perfil'))

            if not nova_senha or not confirmar_senha:
                flash('Para alterar a senha, preencha os campos de nova senha e confirmação.', 'warning')
                return redirect(url_for('routes.editar_perfil'))

            if not check_password_hash(current_user.password, senha_atual):
                flash('A senha atual está incorreta.', 'danger')
                return redirect(url_for('routes.editar_perfil'))

            if nova_senha != confirmar_senha:
                flash('A nova senha e a confirmação não correspondem.', 'danger')
                return redirect(url_for('routes.editar_perfil'))

            current_user.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            db.session.commit()
            flash('Sua senha foi alterada com sucesso!', 'success')
            return redirect(url_for('routes.editar_perfil'))

    return render_template('editar_perfil.html')

# =============================================================================
# ROTAS DO PAINEL DE ADMINISTRAÇÃO
# =============================================================================

@bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    aba_ativa = request.args.get('aba', 'solicitacoes')
    
    # --- LÓGICA DE FILTRO DE DATA PARA SOLICITAÇÕES ---
    query_solicitacoes = Solicitacao.query

    # Pega as datas da URL (enviadas pelo formulário GET)
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    if data_inicio_str:
        # Converte a string 'YYYY-MM-DD' para um objeto datetime no início do dia
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        # Filtra as solicitações cuja data de chegada é maior ou igual à data de início
        query_solicitacoes = query_solicitacoes.filter(Solicitacao.horario_chegada >= data_inicio)

    if data_fim_str:
        # Converte a string para datetime e adiciona o horário final do dia para incluir o dia todo
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        # Filtra as solicitações cuja data de chegada é menor ou igual à data de fim
        query_solicitacoes = query_solicitacoes.filter(Solicitacao.horario_chegada <= data_fim)
    
    # --- FIM DA LÓGICA DE FILTRO ---

     # --- CÁLCULO DOS KPIs PARA OS CARTÕES DE RESUMO ---
    kpis = {
        'solicitacoes_pendentes': Solicitacao.query.filter_by(status='Pendente').count(),
        'viagens_em_andamento': Viagem.query.filter_by(status='Em Andamento').count(),
        'motoristas_disponiveis': Motorista.query.filter_by(status='Disponível').count(),
        'total_motoristas': Motorista.query.count()
    }
    # --- FIM DO CÁLCULO DOS KPIs ---

    dados = {
        'motoristas': Motorista.query.order_by(Motorista.nome).all(),
        'supervisores': Supervisor.query.order_by(Supervisor.nome).all(),
        'colaboradores': Colaborador.query.order_by(Colaborador.nome).all(),
        'solicitacoes': query_solicitacoes.order_by(Solicitacao.id.desc()).all(),
        'blocos': Bloco.query.order_by(Bloco.codigo_bloco).all()
    }
    
    return render_template('admin_dashboard.html', 
                           dados=dados, 
                           kpis=kpis,  # Passa os KPIs para o template
                           aba_ativa=aba_ativa,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str)





# --- ROTAS DE CADASTRO ---

@bp.route('/admin/cadastrar_bloco', methods=['GET', 'POST'])
@login_required
def cadastrar_bloco():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))
    
    if request.method == 'POST':
        codigo = request.form.get('codigo_bloco')
        valor = request.form.get('valor')
        valor_repasse = request.form.get('valor_repasse')

        if Bloco.query.filter_by(codigo_bloco=codigo).first():
            flash(f'O código de bloco "{codigo}" já existe.', 'warning')
            return redirect(url_for('routes.cadastrar_bloco'))

        novo_bloco = Bloco(codigo_bloco=codigo, valor=float(valor), valor_repasse=float(valor_repasse))
        db.session.add(novo_bloco)
        db.session.commit()
        flash(f'Bloco "{codigo}" cadastrado com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='blocos'))

    return render_template('cadastrar_bloco.html')

@bp.route('/admin/editar_bloco/<int:bloco_id>', methods=['GET', 'POST'])
@login_required
def editar_bloco(bloco_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    bloco = Bloco.query.get_or_404(bloco_id)

    if request.method == 'POST':
        novo_codigo = request.form.get('codigo_bloco')
        novo_valor = request.form.get('valor')
        novo_valor_repasse = request.form.get('valor_repasse')

        bloco_existente = Bloco.query.filter(Bloco.codigo_bloco == novo_codigo, Bloco.id != bloco_id).first()
        if bloco_existente:
            flash(f'O código de bloco "{novo_codigo}" já está em uso por outro registro.', 'warning')
            return redirect(url_for('routes.editar_bloco', bloco_id=bloco_id))

        bloco.codigo_bloco = novo_codigo
        bloco.valor = float(novo_valor)
        bloco.valor_repasse = float(novo_valor_repasse)

        db.session.commit()
        flash(f'Bloco "{bloco.codigo_bloco}" atualizado com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='blocos'))

    return render_template('editar_bloco.html', bloco=bloco)

@bp.route('/admin/excluir_bloco/<int:bloco_id>', methods=['POST'])
@login_required
def excluir_bloco(bloco_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    bloco = Bloco.query.get_or_404(bloco_id)
    
    db.session.delete(bloco)
    db.session.commit()
    
    flash(f'Bloco "{bloco.codigo_bloco}" excluído com sucesso.', 'success')
    return redirect(url_for('routes.admin_dashboard', aba='blocos'))

@bp.route('/admin/cadastrar_colaborador', methods=['GET', 'POST'])
@login_required
def cadastrar_colaborador():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        planta = request.form.get('planta')
        bloco_id = request.form.get('bloco_id')

        if not nome or not planta or not bloco_id:
            flash('Os campos Nome, Planta e Bloco são obrigatórios.', 'warning')
            blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
            return render_template('cadastrar_colaborador.html', blocos=blocos)

        novo_colaborador = Colaborador(
            nome=nome,
            planta=planta,
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            telefone=request.form.get('telefone'),
            email=request.form.get('email'),
            turno=request.form.get('turno'),
            bloco_id=int(bloco_id) if bloco_id else None
        )
        db.session.add(novo_colaborador)
        db.session.commit()
        flash(f'Colaborador "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='colaboradores'))

    blocos_disponiveis = Bloco.query.order_by(Bloco.codigo_bloco).all()
    return render_template('cadastrar_colaborador.html', blocos=blocos_disponiveis)





# =============================================================================
# ROTA DE EXPORTAÇÃO CSV 
# =============================================================================


@bp.route('/admin/exportar_solicitacoes_csv')
@login_required
def exportar_solicitacoes_csv():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    # --- LÓGICA DE FILTRO DE DATA (permanece a mesma) ---
    query_solicitacoes = Solicitacao.query
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        query_solicitacoes = query_solicitacoes.filter(Solicitacao.horario_chegada >= data_inicio)

    if data_fim_str:
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query_solicitacoes = query_solicitacoes.filter(Solicitacao.horario_chegada <= data_fim)
    
    solicitacoes_filtradas = query_solicitacoes.order_by(Solicitacao.id.desc()).all()
    
    # --- NOVA LÓGICA DE GERAÇÃO DO CSV ---
    # 1. Cria um buffer de memória
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    # 2. Escreve o cabeçalho
    cabecalho = [
        'ID Viagem', 'ID Solicitacao', 'Status', 'Tipo Corrida', 'Data Chegada',
        'Colaborador', 'Planta', 'Bloco', 'Supervisor', 'Motorista',
        'Valor (R$)', 'Valor Repasse (R$)'
    ]
    writer.writerow(cabecalho)

    # 3. Escreve todas as linhas de dados
    for solicitacao in solicitacoes_filtradas:
        bloco = solicitacao.colaborador.bloco
        linha = [
            solicitacao.viagem_id or '',
            solicitacao.id,
            solicitacao.status,
            solicitacao.tipo_corrida,
            solicitacao.horario_chegada.strftime('%d/%m/%Y %H:%M'),
            solicitacao.colaborador.nome,
            solicitacao.colaborador.planta,
            bloco.codigo_bloco if bloco else '',
            solicitacao.supervisor.nome,
            solicitacao.viagem.motorista.nome if solicitacao.viagem and solicitacao.viagem.motorista else '',
            f'{bloco.valor:.2f}' if bloco else '0.00',
            f'{bloco.valor_repasse:.2f}' if bloco else '0.00'
        ]
        writer.writerow(linha)

    # 4. Pega todo o conteúdo do buffer de memória
    csv_content = output.getvalue()

    # 5. Cria a resposta para o navegador forçar o download
    nome_arquivo = f"solicitacoes_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={nome_arquivo}"}
    )
















# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================
# ROTAS DO SUPERVISOR (a serem implementadas)
# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================


@bp.route('/admin/cadastrar_supervisor', methods=['GET', 'POST'])
@login_required
def cadastrar_supervisor():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        nome = request.form.get('nome')
        planta = request.form.get('planta')

        if not email or not senha or not nome or not planta:
            flash('Os campos E-mail, Senha, Nome e Planta são obrigatórios.', 'warning')
            blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
            return render_template('cadastrar_supervisor.html', blocos=blocos)

        if User.query.filter_by(email=email).first():
            flash('Este e-mail de acesso já está cadastrado. Tente outro.', 'warning')
            blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
            return render_template('cadastrar_supervisor.html', blocos=blocos)

        hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, role='supervisor')
        db.session.add(new_user)
        db.session.commit()

        novo_supervisor = Supervisor(
            user_id=new_user.id,
            nome=nome,
            planta=planta,
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            telefone=request.form.get('telefone'),
            turno=request.form.get('turno'),
            gerente_responsavel=request.form.get('gerente_responsavel'),
            bloco_id=int(request.form.get('bloco_id')) if request.form.get('bloco_id') else None
        )
        db.session.add(novo_supervisor)
        db.session.commit()
        flash(f'Supervisor "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='supervisores'))

    blocos_disponiveis = Bloco.query.order_by(Bloco.codigo_bloco).all()
    return render_template('cadastrar_supervisor.html', blocos=blocos_disponiveis)



@bp.route('/admin/editar_supervisor/<int:supervisor_id>', methods=['GET', 'POST'])
@login_required
def editar_supervisor(supervisor_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    supervisor = Supervisor.query.get_or_404(supervisor_id)
    
    if request.method == 'POST':
        # Atualiza os campos do perfil
        supervisor.nome = request.form.get('nome')
        supervisor.planta = request.form.get('planta')
        # ... (adicione todos os outros campos do supervisor aqui) ...
        supervisor.bloco_id = int(request.form.get('bloco_id')) if request.form.get('bloco_id') else None
        
        # Atualiza o e-mail (login) se for alterado
        novo_email = request.form.get('email')
        if novo_email != supervisor.user.email:
            if User.query.filter(User.email == novo_email, User.id != supervisor.user_id).first():
                flash('O novo e-mail já está em uso por outra conta.', 'warning')
                return redirect(url_for('routes.editar_supervisor', supervisor_id=supervisor.id))
            supervisor.user.email = novo_email

        db.session.commit()
        flash(f'Dados do supervisor "{supervisor.nome}" atualizados!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='supervisores'))

    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
    return render_template('editar_supervisor.html', supervisor=supervisor, blocos=blocos)


@bp.route('/admin/excluir_supervisor/<int:supervisor_id>', methods=['POST'])
@login_required
def excluir_supervisor(supervisor_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    supervisor = Supervisor.query.get_or_404(supervisor_id)
    
    if Solicitacao.query.filter_by(supervisor_id=supervisor.id).first():
        flash(f'Não é possível excluir o supervisor "{supervisor.nome}", pois ele possui solicitações associadas.', 'danger')
        return redirect(url_for('routes.admin_dashboard', aba='supervisores'))
        
    # Importante: Excluir o perfil do supervisor e também o seu usuário de login
    user_para_excluir = supervisor.user
    nome_supervisor = supervisor.nome
    
    db.session.delete(supervisor)
    db.session.delete(user_para_excluir)
    db.session.commit()
    
    flash(f'Supervisor "{nome_supervisor}" e seu usuário de acesso foram excluídos.', 'success')
    return redirect(url_for('routes.admin_dashboard', aba='supervisores'))





@bp.route('/dashboard/supervisor')
@login_required
def dashboard_supervisor():
    if current_user.role != 'supervisor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    # Garante que o usuário logado tem um perfil de supervisor associado
    supervisor_profile = current_user.supervisor
    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado. Contate o administrador.', 'danger')
        return redirect(url_for('routes.logout'))

    # Busca o histórico de solicitações feitas por este supervisor
    solicitacoes_feitas = Solicitacao.query.filter_by(supervisor_id=supervisor_profile.id).order_by(Solicitacao.id.desc()).all()

    return render_template('dashboard_supervisor.html', solicitacoes=solicitacoes_feitas)




@bp.route('/supervisor/nova_solicitacao', methods=['GET', 'POST'])
@login_required
def nova_solicitacao():
    if current_user.role != 'supervisor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    supervisor_profile = current_user.supervisor
    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado.', 'danger')
        return redirect(url_for('routes.logout'))

    # Busca apenas os colaboradores da mesma planta do supervisor
    colaboradores_da_planta = Colaborador.query.filter_by(planta=supervisor_profile.planta).order_by(Colaborador.nome).all()

    if request.method == 'POST':
        colaborador_id = request.form.get('colaborador_id')
        tipo_corrida = request.form.get('tipo_corrida')
        horario_chegada_str = request.form.get('horario_chegada')

        if not colaborador_id or not tipo_corrida or not horario_chegada_str:
            flash('Todos os campos são obrigatórios.', 'warning')
            return render_template('nova_solicitacao.html', colaboradores=colaboradores_da_planta)

        # Converte a string do formulário para um objeto datetime
        horario_chegada = datetime.fromisoformat(horario_chegada_str)

        nova_solicitacao = Solicitacao(
            colaborador_id=int(colaborador_id),
            supervisor_id=supervisor_profile.id,
            tipo_corrida=tipo_corrida,
            horario_chegada=horario_chegada
        )
        db.session.add(nova_solicitacao)
        db.session.commit()

        flash('Nova solicitação de transporte criada com sucesso!', 'success')
        return redirect(url_for('routes.dashboard_supervisor'))

    # Se for GET, apenas mostra o formulário
    return render_template('nova_solicitacao.html', colaboradores=colaboradores_da_planta)




@bp.route('/supervisor/cancelar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def cancelar_solicitacao(solicitacao_id):
    """Permite que um supervisor cancele uma solicitação que ele mesmo criou."""
    if current_user.role != 'supervisor':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    # Busca a solicitação no banco de dados
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    
    # Busca o perfil do supervisor logado
    supervisor_profile = current_user.supervisor
    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado.', 'danger')
        return redirect(url_for('routes.logout'))

    # --- VERIFICAÇÕES DE SEGURANÇA ---
    # 1. O supervisor só pode cancelar suas próprias solicitações.
    if solicitacao.supervisor_id != supervisor_profile.id:
        flash('Você não tem permissão para cancelar esta solicitação.', 'danger')
        return redirect(url_for('routes.dashboard_supervisor'))

    # 2. A solicitação só pode ser cancelada se ainda estiver 'Pendente'.
    if solicitacao.status != 'Pendente':
        flash('Esta solicitação não pode mais ser cancelada, pois já foi aceita por um motorista.', 'warning')
        return redirect(url_for('routes.dashboard_supervisor'))

    # --- LÓGICA DE CANCELAMENTO ---
    solicitacao.status = 'Cancelada'
    db.session.commit()

    flash(f'A solicitação para o colaborador "{solicitacao.colaborador.nome}" foi cancelada com sucesso.', 'success')
    return redirect(url_for('routes.dashboard_supervisor'))






# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================
# ROTAS DO COLABORADOR 
# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================




@bp.route('/admin/editar_colaborador/<int:colaborador_id>', methods=['GET', 'POST'])
@login_required
def editar_colaborador(colaborador_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    colaborador = Colaborador.query.get_or_404(colaborador_id)
    
    if request.method == 'POST':
        # Atualiza os campos do objeto com os dados do formulário
        colaborador.nome = request.form.get('nome')
        colaborador.planta = request.form.get('planta')
        colaborador.endereco = request.form.get('endereco')
        colaborador.nro = request.form.get('nro')
        colaborador.bairro = request.form.get('bairro')
        colaborador.cidade = request.form.get('cidade')
        colaborador.uf = request.form.get('uf')
        colaborador.telefone = request.form.get('telefone')
        colaborador.email = request.form.get('email')
        colaborador.turno = request.form.get('turno')
        colaborador.bloco_id = int(request.form.get('bloco_id')) if request.form.get('bloco_id') else None
        
        db.session.commit()
        flash(f'Dados do colaborador "{colaborador.nome}" atualizados com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='colaboradores'))

    # Se for GET, busca os blocos e renderiza o formulário de edição
    blocos_disponiveis = Bloco.query.order_by(Bloco.codigo_bloco).all()
    return render_template('editar_colaborador.html', colaborador=colaborador, blocos=blocos_disponiveis)


@bp.route('/admin/excluir_colaborador/<int:colaborador_id>', methods=['POST'])
@login_required
def excluir_colaborador(colaborador_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    colaborador = Colaborador.query.get_or_404(colaborador_id)
    
    # Verificação de segurança: impede a exclusão se o colaborador tiver solicitações associadas
    if Solicitacao.query.filter_by(colaborador_id=colaborador.id).first():
        flash(f'Não é possível excluir o colaborador "{colaborador.nome}", pois ele possui solicitações de transporte associadas.', 'danger')
        return redirect(url_for('routes.admin_dashboard', aba='colaboradores'))
        
    nome_colaborador = colaborador.nome
    db.session.delete(colaborador)
    db.session.commit()
    
    flash(f'Colaborador "{nome_colaborador}" excluído com sucesso.', 'success')
    return redirect(url_for('routes.admin_dashboard', aba='colaboradores'))





















# =============================================================================
# =============================================================================
# =============================================================================
#       ROTAS DO MOTORISTA (Do Painel do Admin e das telas do Motorista)
# =============================================================================
# =============================================================================
# =============================================================================



@bp.route('/admin/cadastrar_motorista', methods=['GET', 'POST'])
@login_required
def cadastrar_motorista():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        nome = request.form.get('nome')
        placa_veiculo = request.form.get('placa_veiculo')

        if not email or not senha or not nome or not placa_veiculo:
            flash('Os campos E-mail, Senha, Nome e Placa do Veículo são obrigatórios.', 'warning')
            return render_template('cadastrar_motorista.html')

        if User.query.filter_by(email=email).first():
            flash('Este e-mail de acesso já está em uso. Tente outro.', 'warning')
            return render_template('cadastrar_motorista.html')
        
        if Motorista.query.filter_by(placa_veiculo=placa_veiculo).first():
            flash(f'A placa "{placa_veiculo}" já está cadastrada em outro motorista.', 'warning')
            return render_template('cadastrar_motorista.html')

        hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, role='motorista')
        db.session.add(new_user)
        db.session.commit()

        novo_motorista = Motorista(
            user_id=new_user.id,
            nome=nome,
            planta=request.form.get('planta'),
            telefone=request.form.get('telefone'),
            pix=request.form.get('pix'),
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            veiculo=request.form.get('veiculo'),
            ano_veiculo=int(request.form.get('ano_veiculo')) if request.form.get('ano_veiculo') else None,
            cor_veiculo=request.form.get('cor_veiculo'),
            placa_veiculo=placa_veiculo,
            km_veiculo=float(request.form.get('km_veiculo')) if request.form.get('km_veiculo') else None,
            observacoes_gerais=request.form.get('observacoes_gerais')
        )
        db.session.add(novo_motorista)
        db.session.commit()
        flash(f'Motorista "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='motoristas'))

    return render_template('cadastrar_motorista.html')









@bp.route('/admin/editar_motorista/<int:motorista_id>', methods=['GET', 'POST'])
@login_required
def editar_motorista(motorista_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    # Busca o motorista no banco de dados ou retorna um erro 404
    motorista = Motorista.query.get_or_404(motorista_id)

    if request.method == 'POST':
        # --- Atualiza os campos do perfil do Motorista ---
        motorista.nome = request.form.get('nome')
        motorista.planta = request.form.get('planta')
        motorista.telefone = request.form.get('telefone')
        motorista.pix = request.form.get('pix')
        motorista.endereco = request.form.get('endereco')
        motorista.nro = request.form.get('nro')
        motorista.bairro = request.form.get('bairro')
        motorista.cidade = request.form.get('cidade')
        motorista.uf = request.form.get('uf')
        motorista.veiculo = request.form.get('veiculo')
        motorista.ano_veiculo = int(request.form.get('ano_veiculo')) if request.form.get('ano_veiculo') else None
        motorista.cor_veiculo = request.form.get('cor_veiculo')
        motorista.placa_veiculo = request.form.get('placa_veiculo')
        motorista.km_veiculo = float(request.form.get('km_veiculo')) if request.form.get('km_veiculo') else None
        motorista.observacoes_gerais = request.form.get('observacoes_gerais')

        # --- Atualiza o e-mail (login) na tabela User ---
        novo_email = request.form.get('email')
        if novo_email != motorista.user.email:
            # Verifica se o novo e-mail já não está em uso por OUTRA conta
            if User.query.filter(User.email == novo_email, User.id != motorista.user_id).first():
                flash('O novo e-mail já está em uso por outra conta.', 'warning')
                # Re-renderiza o formulário sem salvar as alterações
                return render_template('editar_motorista.html', motorista=motorista)
            motorista.user.email = novo_email
        
        # --- Lógica para alterar a senha (opcional) ---
        nova_senha = request.form.get('senha')
        if nova_senha:
            motorista.user.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            flash('A senha do motorista foi alterada.', 'info')

        db.session.commit()
        flash(f'Dados do motorista "{motorista.nome}" atualizados com sucesso!', 'success')
        return redirect(url_for('routes.admin_dashboard', aba='motoristas'))

    # Se o método for GET, apenas exibe a página com os dados atuais do motorista
    return render_template('editar_motorista.html', motorista=motorista)



@bp.route('/admin/excluir_motorista/<int:motorista_id>', methods=['POST'])
@login_required
def excluir_motorista(motorista_id):
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    motorista = Motorista.query.get_or_404(motorista_id)
    
    # Verificação de segurança
    if Viagem.query.filter_by(motorista_id=motorista.id).first():
        flash(f'Não é possível excluir o motorista "{motorista.nome}", pois ele possui viagens associadas.', 'danger')
        return redirect(url_for('routes.admin_dashboard', aba='motoristas'))
        
    user_para_excluir = motorista.user
    nome_motorista = motorista.nome
    
    db.session.delete(motorista)
    db.session.delete(user_para_excluir)
    db.session.commit()
    
    flash(f'Motorista "{nome_motorista}" e seu usuário de acesso foram excluídos.', 'success')
    return redirect(url_for('routes.admin_dashboard', aba='motoristas'))





@bp.route('/dashboard/motorista')
@login_required
def dashboard_motorista():
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    motorista_profile = current_user.motorista
    if not motorista_profile:
        flash('Perfil de motorista não encontrado. Contate o administrador.', 'danger')
        return redirect(url_for('routes.logout'))

    # Busca todas as solicitações que estão pendentes e não pertencem a nenhuma viagem
    solicitacoes_pendentes = Solicitacao.query.filter_by(status='Pendente', viagem_id=None).order_by(Solicitacao.horario_chegada).all()

    # Busca a viagem que este motorista específico está fazendo no momento
    viagem_atual = Viagem.query.filter_by(
        motorista_id=motorista_profile.id,
        status='Em Andamento'
    ).first()

    return render_template(
        'dashboard_motorista.html',
        motorista=motorista_profile,
        solicitacoes_pendentes=solicitacoes_pendentes,
        viagem_atual=viagem_atual
    )





@bp.route('/motorista/aceitar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def aceitar_solicitacao(solicitacao_id):
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    motorista_profile = current_user.motorista
    if not motorista_profile:
        flash('Perfil de motorista não encontrado.', 'danger')
        return redirect(url_for('routes.logout'))

    # --- VERIFICAÇÕES DE SEGURANÇA ---
    # 1. Motorista só pode aceitar se estiver 'Disponível'
    if motorista_profile.status != 'Disponível':
        flash('Você precisa finalizar sua viagem atual antes de aceitar uma nova solicitação.', 'warning')
        return redirect(url_for('routes.dashboard_motorista'))

    # 2. Busca a solicitação e verifica se ela ainda está disponível
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    if solicitacao.status != 'Pendente' or solicitacao.viagem_id is not None:
        flash('Esta solicitação não está mais disponível.', 'warning')
        return redirect(url_for('routes.dashboard_motorista'))

    # --- LÓGICA DE ACEITE E CRIAÇÃO DA VIAGEM ---
    # 1. Cria uma nova Viagem (o contêiner)
    nova_viagem = Viagem(
        motorista_id=motorista_profile.id,
        status='Em Andamento'
    )
    db.session.add(nova_viagem)
    
    # 2. Atualiza o status do motorista
    motorista_profile.status = 'Ocupado'
    
    # 3. Associa a solicitação à nova viagem e atualiza seu status
    solicitacao.viagem = nova_viagem
    solicitacao.status = 'Agendada'
    
    # Salva todas as alterações no banco de dados
    db.session.commit()

    flash(f'Você aceitou a solicitação para {solicitacao.colaborador.nome}. Boa viagem!', 'success')
    return redirect(url_for('routes.dashboard_motorista'))



@bp.route('/motorista/finalizar_viagem/<int:viagem_id>', methods=['POST'])
@login_required
def finalizar_viagem(viagem_id):
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    motorista_profile = current_user.motorista
    if not motorista_profile:
        flash('Perfil de motorista não encontrado.', 'danger')
        return redirect(url_for('routes.logout'))

    # Busca a viagem no banco de dados
    viagem = Viagem.query.get_or_404(viagem_id)

    # --- VERIFICAÇÕES DE SEGURANÇA ---
    # 1. Garante que o motorista só pode finalizar a sua própria viagem.
    if viagem.motorista_id != motorista_profile.id:
        flash('Você não tem permissão para finalizar esta viagem.', 'danger')
        return redirect(url_for('routes.dashboard_motorista'))

    # 2. Garante que a viagem está 'Em Andamento'.
    if viagem.status != 'Em Andamento':
        flash('Esta viagem não pode ser finalizada neste estado.', 'warning')
        return redirect(url_for('routes.dashboard_motorista'))

    # --- LÓGICA DE FINALIZAÇÃO ---
    # 1. Atualiza a viagem
    viagem.status = 'Finalizada'
    viagem.data_finalizacao = datetime.utcnow()

    # 2. Libera o motorista
    motorista_profile.status = 'Disponível'

    # 3. Atualiza todas as solicitações dentro da viagem
    for solicitacao in viagem.solicitacoes:
        solicitacao.status = 'Finalizada'
    
    # Salva todas as alterações no banco de dados
    db.session.commit()

    flash('Viagem finalizada com sucesso! Você está disponível para novas corridas.', 'success')
    return redirect(url_for('routes.dashboard_motorista'))




@bp.route('/motorista/agrupar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def agrupar_solicitacao(solicitacao_id):
    if current_user.role != 'motorista':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('routes.home'))

    motorista_profile = current_user.motorista
    if not motorista_profile:
        flash('Perfil de motorista não encontrado.', 'danger')
        return redirect(url_for('routes.logout'))

    # --- VERIFICAÇÕES DE SEGURANÇA ---
    # 1. Motorista precisa estar 'Ocupado' para agrupar
    if motorista_profile.status != 'Ocupado':
        flash('Você precisa estar em uma viagem para agrupar solicitações.', 'warning')
        return redirect(url_for('routes.dashboard_motorista'))

    # 2. Busca a viagem atual do motorista
    viagem_atual = Viagem.query.filter_by(motorista_id=motorista_profile.id, status='Em Andamento').first()
    if not viagem_atual:
        flash('Não foi possível encontrar sua viagem atual. Contate o suporte.', 'danger')
        return redirect(url_for('routes.dashboard_motorista'))

    # 3. Busca a solicitação a ser agrupada e verifica seu status
    solicitacao_para_agrupar = Solicitacao.query.get_or_404(solicitacao_id)
    if solicitacao_para_agrupar.status != 'Pendente' or solicitacao_para_agrupar.viagem_id is not None:
        flash('Esta solicitação não está mais disponível para agrupamento.', 'warning')
        return redirect(url_for('routes.dashboard_motorista'))

    # --- LÓGICA DA REGRA DE NEGÓCIO (2 HORAS) ---
    # 1. Encontra a primeira solicitação da viagem (a mais antiga)
    primeira_solicitacao = min(viagem_atual.solicitacoes, key=lambda s: s.horario_chegada)
    
    # 2. Calcula o horário limite para agrupamento
    horario_limite = primeira_solicitacao.horario_chegada - timedelta(hours=2)

    # 3. Compara o horário da nova solicitação com o limite
    if solicitacao_para_agrupar.horario_chegada < horario_limite:
        flash(f'Não é possível agrupar. O horário de chegada ({solicitacao_para_agrupar.horario_chegada.strftime("%H:%M")}) é muito anterior ao limite de 2 horas da sua viagem atual ({horario_limite.strftime("%H:%M")}).', 'danger')
        return redirect(url_for('routes.dashboard_motorista'))

    # --- LÓGICA DE AGRUPAMENTO ---
    # Se todas as regras passaram, associa a solicitação à viagem atual
    solicitacao_para_agrupar.viagem_id = viagem_atual.id
    solicitacao_para_agrupar.status = 'Agendada'
    
    db.session.commit()

    flash(f'Solicitação para {solicitacao_para_agrupar.colaborador.nome} agrupada com sucesso na sua viagem atual!', 'success')
    return redirect(url_for('routes.dashboard_motorista'))











