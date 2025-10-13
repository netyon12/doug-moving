# Em app/blueprints/gerente.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from ..models import Solicitacao, Supervisor, Colaborador, Viagem, Bloco
from ..decorators import permission_required
from datetime import datetime, date
from sqlalchemy import func

gerente_bp = Blueprint('gerente', __name__, url_prefix='/gerente')

@gerente_bp.route('/dashboard')
@login_required
@permission_required(['gerente'])
def dashboard_gerente():
    if current_user.role != 'gerente':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    gerente_profile = current_user.gerente
    if not gerente_profile:
        flash('Perfil de gerente não encontrado. Contate o administrador.', 'danger')
        return redirect(url_for('auth.logout'))

    # Obter IDs dos supervisores gerenciados
    ids_supervisores = [s.id for s in Supervisor.query.filter_by(gerente_id=gerente_profile.id).all()]

    # KPI 1: Solicitações Pendentes
    solicitacoes_pendentes = Solicitacao.query.filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Solicitacao.status == 'Pendente'
    ).count()

    # KPI 2: Solicitações Agendadas
    solicitacoes_agendadas = Solicitacao.query.filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Solicitacao.status == 'Agendada'
    ).count()

    # KPI 3: Viagens em Andamento (buscar através das solicitações)
    from ..models import db
    viagens_andamento = db.session.query(Viagem).join(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Viagem.status == 'Em Andamento'
    ).distinct().count()

    # KPI 4: Taxa de Ocupação Média (calcular com base nas solicitações)
    # Buscar configuração de max_passageiros
    from ..models import Configuracao
    config_max_pass = Configuracao.query.filter_by(chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
    max_passageiros = int(config_max_pass.valor) if config_max_pass else 4
    
    # Calcular taxa de ocupação média das viagens agendadas/em andamento
    viagens_ativas = db.session.query(Viagem).join(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Viagem.status.in_(['Agendada', 'Em Andamento'])
    ).distinct().all()
    
    if viagens_ativas:
        taxas = []
        for viagem in viagens_ativas:
            num_passageiros = len(viagem.solicitacoes)
            taxa = (num_passageiros / max_passageiros) * 100 if max_passageiros > 0 else 0
            taxas.append(taxa)
        taxa_ocupacao_media = sum(taxas) / len(taxas) if taxas else 0
    else:
        taxa_ocupacao_media = 0

    # KPI 5: Finalizadas Hoje
    hoje = date.today()
    finalizadas_hoje = Solicitacao.query.filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Solicitacao.status == 'Finalizada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    # KPI 6: Canceladas Hoje
    canceladas_hoje = Solicitacao.query.filter(
        Solicitacao.supervisor_id.in_(ids_supervisores),
        Solicitacao.status == 'Cancelada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    # KPI 7: Total de Supervisores Ativos
    total_supervisores = len(ids_supervisores)

    # KPI 8: Total de Colaboradores da Planta
    total_colaboradores = Colaborador.query.filter_by(
        planta_id=gerente_profile.planta_id
    ).count()

    return render_template(
        'dashboard_gerente.html',
        solicitacoes_pendentes=solicitacoes_pendentes,
        solicitacoes_agendadas=solicitacoes_agendadas,
        viagens_andamento=viagens_andamento,
        taxa_ocupacao_media=taxa_ocupacao_media,
        finalizadas_hoje=finalizadas_hoje,
        canceladas_hoje=canceladas_hoje,
        total_supervisores=total_supervisores,
        total_colaboradores=total_colaboradores
    )


@gerente_bp.route('/solicitacoes')
@login_required
@permission_required(['gerente'])
def solicitacoes():
    """Rota para listar solicitações do gerente"""
    if current_user.role != 'gerente':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    gerente_profile = current_user.gerente
    if not gerente_profile:
        flash('Perfil de gerente não encontrado.', 'danger')
        return redirect(url_for('auth.logout'))

    # Obter IDs dos supervisores gerenciados
    ids_supervisores = [s.id for s in Supervisor.query.filter_by(gerente_id=gerente_profile.id).all()]

    # Query base
    query = Solicitacao.query.filter(Solicitacao.supervisor_id.in_(ids_supervisores))

    # Aplicar filtros
    id_solicitacao = request.args.get('id_solicitacao')
    colaborador_nome = request.args.get('colaborador_nome')
    colaborador_matricula = request.args.get('colaborador_matricula')
    viagem_id = request.args.get('viagem_id')
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    supervisor_id = request.args.get('supervisor_id')
    bloco_id = request.args.get('bloco_id')
    planta = request.args.get('planta')

    if id_solicitacao:
        query = query.filter(Solicitacao.id == int(id_solicitacao))
    
    if colaborador_nome:
        query = query.join(Colaborador).filter(
            Colaborador.nome.ilike(f'%{colaborador_nome}%')
        )
    
    if colaborador_matricula:
        query = query.join(Colaborador).filter(
            Colaborador.matricula.ilike(f'%{colaborador_matricula}%')
        )
    
    if viagem_id:
        query = query.filter(Solicitacao.viagem_id == int(viagem_id))
    
    if status:
        query = query.filter(Solicitacao.status == status)
    
    if data_inicio:
        data_inicio_dt = datetime.strptime(data_inicio, '%Y-%m-%d')
        query = query.filter(Solicitacao.data_criacao >= data_inicio_dt)
    
    if data_fim:
        data_fim_dt = datetime.strptime(data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Solicitacao.data_criacao <= data_fim_dt)
    
    if supervisor_id:
        query = query.filter(Solicitacao.supervisor_id == int(supervisor_id))
    
    if bloco_id:
        query = query.filter(Solicitacao.bloco_id == int(bloco_id))
    
    if planta:
        query = query.join(Colaborador).filter(
            Colaborador.planta.ilike(f'%{planta}%')
        )

    # Executar query
    solicitacoes = query.order_by(Solicitacao.id.desc()).all()

    # Buscar supervisores e blocos para os filtros
    todos_supervisores = Supervisor.query.filter(Supervisor.id.in_(ids_supervisores)).order_by(Supervisor.nome).all()
    todos_blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()

    return render_template(
        'solicitacoes_gerente.html',
        solicitacoes=solicitacoes,
        todos_supervisores=todos_supervisores,
        todos_blocos=todos_blocos,
        filtros=request.args
    )


@gerente_bp.route('/solicitacoes/<int:id>/visualizar')
@login_required
@permission_required(['gerente'])
def visualizar_solicitacao(id):
    """Rota para visualizar uma solicitação (somente leitura)"""
    if current_user.role != 'gerente':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    solicitacao = Solicitacao.query.get_or_404(id)
    
    # Verifica se a solicitação pertence a um supervisor gerenciado
    gerente_profile = current_user.gerente
    ids_supervisores = [s.id for s in Supervisor.query.filter_by(gerente_id=gerente_profile.id).all()]
    
    if solicitacao.supervisor_id not in ids_supervisores:
        flash('Você não tem permissão para visualizar esta solicitação.', 'danger')
        return redirect(url_for('gerente.solicitacoes'))
    
    return render_template('visualizar_solicitacao_gerente.html', solicitacao=solicitacao)

