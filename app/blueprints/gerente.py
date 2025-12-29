# app/blueprints/gerente.py

from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from ..models import Solicitacao, Supervisor, Colaborador, Viagem, Bloco, Motorista
from ..decorators import permission_required
from ..config.tenant_utils import query_tenant, get_tenant_session
from datetime import datetime, date
from sqlalchemy import func

gerente_bp = Blueprint('gerente', __name__, url_prefix='/gerente')


@gerente_bp.route('/dashboard')
@login_required
@permission_required(['gerente'])
def dashboard_gerente():
    """Dashboard do Gerente com KPIs coloridos e dados do banco tenant correto"""
    
    if current_user.role != 'gerente':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    # CORREÇÃO: Buscar gerente usando query_tenant
    gerente_profile = query_tenant(current_user.__class__).get(current_user.id)
    if not gerente_profile or not hasattr(gerente_profile, 'gerente'):
        flash('Perfil de gerente não encontrado. Contate o administrador.', 'danger')
        return redirect(url_for('auth.logout'))
    
    gerente_data = gerente_profile.gerente

    # Obter IDs dos supervisores gerenciados (do banco tenant)
    supervisores = query_tenant(Supervisor).filter_by(
        gerente_id=gerente_data.id
    ).all()
    ids_supervisores = [s.id for s in supervisores]

    # ========== KPIs DE SOLICITAÇÕES ==========
    
    # Solicitações Pendentes
    solicitacoes_pendentes = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False,
        Solicitacao.status == 'Pendente'
    ).count() if ids_supervisores else 0

    # Solicitações Agendadas
    solicitacoes_agendadas = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False,
        Solicitacao.status == 'Agendada'
    ).count() if ids_supervisores else 0

    # Solicitações Em Andamento
    solicitacoes_andamento = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False,
        Solicitacao.status == 'Em Andamento'
    ).count() if ids_supervisores else 0

    # Solicitações Finalizadas (Hoje)
    hoje = date.today()
    solicitacoes_finalizadas_hoje = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False,
        Solicitacao.status == 'Finalizada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count() if ids_supervisores else 0

    # ========== KPIs DE VIAGENS ==========
    
    # Buscar IDs de viagens das solicitações dos supervisores
    if ids_supervisores:
        viagens_ids = get_tenant_session().query(Solicitacao.viagem_id).filter(
            Solicitacao.supervisor_id.in_(ids_supervisores),
            Solicitacao.viagem_id.isnot(None)
        ).distinct().all()
        viagens_ids = [v[0] for v in viagens_ids]
    else:
        viagens_ids = []

    # Viagens Pendentes
    viagens_pendentes = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids) if viagens_ids else False,
        Viagem.status == 'Pendente'
    ).count() if viagens_ids else 0

    # Viagens Agendadas
    viagens_agendadas = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids) if viagens_ids else False,
        Viagem.status == 'Agendada'
    ).count() if viagens_ids else 0

    # Viagens Em Andamento
    viagens_andamento = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids) if viagens_ids else False,
        Viagem.status == 'Em Andamento'
    ).count() if viagens_ids else 0

    # Viagens Finalizadas (Hoje)
    viagens_finalizadas_hoje = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids) if viagens_ids else False,
        Viagem.status == 'Finalizada',
        func.date(Viagem.data_finalizacao) == hoje
    ).count() if viagens_ids else 0

    # ========== KPIs DE RECURSOS ==========
    
    # Total de Colaboradores (CORREÇÃO: buscar do banco tenant)
    # Buscar plantas do gerente
    plantas_ids = []
    if hasattr(gerente_data, 'plantas'):
        plantas_ids = [p.id for p in gerente_data.plantas.all()]
    
    if plantas_ids:
        total_colaboradores = query_tenant(Colaborador).filter(
            Colaborador.planta_id.in_(plantas_ids)
        ).count()
    else:
        # Se não tem plantas específicas, contar todos os colaboradores do tenant
        total_colaboradores = query_tenant(Colaborador).count()

    # Motoristas Ativos (status = 'Disponível' ou 'Ocupado')
    motoristas_ativos = query_tenant(Motorista).filter(
        Motorista.status.in_(['Disponível', 'Ocupado'])
    ).count()

    # Total de Supervisores Ativos
    total_supervisores = len(ids_supervisores)

    # Canceladas Hoje
    canceladas_hoje = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False,
        Solicitacao.status == 'Cancelada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count() if ids_supervisores else 0

    return render_template(
        'gerente/dashboard_gerente.html',
        # KPIs de Solicitações
        solicitacoes_pendentes=solicitacoes_pendentes,
        solicitacoes_agendadas=solicitacoes_agendadas,
        solicitacoes_andamento=solicitacoes_andamento,
        solicitacoes_finalizadas_hoje=solicitacoes_finalizadas_hoje,
        # KPIs de Viagens
        viagens_pendentes=viagens_pendentes,
        viagens_agendadas=viagens_agendadas,
        viagens_andamento=viagens_andamento,
        viagens_finalizadas_hoje=viagens_finalizadas_hoje,
        # KPIs de Recursos
        total_colaboradores=total_colaboradores,
        motoristas_ativos=motoristas_ativos,
        total_supervisores=total_supervisores,
        canceladas_hoje=canceladas_hoje
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

    # Buscar supervisores do gerente (do banco tenant)
    supervisores = query_tenant(Supervisor).filter_by(
        gerente_id=gerente_profile.id
    ).all()
    ids_supervisores = [s.id for s in supervisores]

    # Query base (do banco tenant)
    query = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id.in_(ids_supervisores) if ids_supervisores else False
    ) if ids_supervisores else query_tenant(Solicitacao).filter(False)

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
        data_fim_dt = datetime.strptime(
            data_fim, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(Solicitacao.data_criacao <= data_fim_dt)

    if supervisor_id:
        query = query.filter(Solicitacao.supervisor_id == int(supervisor_id))

    if bloco_id:
        query = query.filter(Solicitacao.bloco_id == int(bloco_id))

    if planta:
        from ..models import Planta
        query = query.join(Colaborador).join(Planta).filter(
            Planta.nome.ilike(f'%{planta}%')
        )

    # Executar query
    solicitacoes = query.order_by(Solicitacao.id.desc()).all()

    # Buscar supervisores e blocos para os filtros (do banco tenant)
    todos_supervisores = query_tenant(Supervisor).filter(
        Supervisor.id.in_(ids_supervisores) if ids_supervisores else False
    ).order_by(Supervisor.nome).all() if ids_supervisores else []
    
    todos_blocos = query_tenant(Bloco).order_by(Bloco.codigo_bloco).all()

    return render_template(
        'gerente/solicitacoes_gerente.html',
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

    # Buscar solicitação do banco tenant
    solicitacao = query_tenant(Solicitacao).get(id)
    if not solicitacao:
        flash('Solicitação não encontrada.', 'danger')
        return redirect(url_for('gerente.solicitacoes'))

    # Verifica se a solicitação pertence a um supervisor gerenciado
    gerente_profile = current_user.gerente
    supervisores = query_tenant(Supervisor).filter_by(
        gerente_id=gerente_profile.id
    ).all()
    ids_supervisores = [s.id for s in supervisores]

    if solicitacao.supervisor_id not in ids_supervisores:
        flash('Você não tem permissão para visualizar esta solicitação.', 'danger')
        return redirect(url_for('gerente.solicitacoes'))

    return render_template('gerente/visualizar_solicitacao_gerente.html', solicitacao=solicitacao)
