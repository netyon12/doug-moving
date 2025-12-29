# app/blueprints/supervisor.py
from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import func

from .. import db
from ..models import User, Supervisor, Colaborador, Motorista, Bloco, Viagem, Solicitacao, Configuracao
from ..decorators import permission_required
from ..models import Empresa
from ..config.tenant_utils import query_tenant, get_tenant_session, get_or_404_tenant
from io import StringIO
import csv

supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')


@supervisor_bp.route('/dashboard')
@login_required
@permission_required('supervisor')
def dashboard_supervisor():
    """Dashboard do Supervisor com KPIs coloridos e separados por Solicitações e Viagens"""
    
    # Buscar supervisor usando query_tenant
    supervisor_profile = query_tenant(Supervisor).filter_by(user_id=current_user.id).first()
    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado.', 'danger')
        return redirect(url_for('auth.logout'))

    # ========== KPIs DE SOLICITAÇÕES ==========
    
    # Solicitações Pendentes
    solicitacoes_pendentes = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Pendente'
    ).count()

    # Solicitações Agendadas
    solicitacoes_agendadas = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Agendada'
    ).count()

    # Solicitações Em Andamento
    solicitacoes_andamento = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Em Andamento'
    ).count()

    # Solicitações Finalizadas (Hoje)
    hoje = date.today()
    solicitacoes_finalizadas_hoje = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Finalizada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    # ========== KPIs DE VIAGENS ==========
    
    # Buscar IDs de viagens das solicitações do supervisor
    viagens_ids = get_tenant_session().query(Solicitacao.viagem_id).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.viagem_id.isnot(None)
    ).distinct().all()
    viagens_ids = [v[0] for v in viagens_ids]

    # Viagens Pendentes
    viagens_pendentes = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids),
        Viagem.status == 'Pendente'
    ).count() if viagens_ids else 0

    # Viagens Agendadas
    viagens_agendadas = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids),
        Viagem.status == 'Agendada'
    ).count() if viagens_ids else 0

    # Viagens Em Andamento
    viagens_andamento = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids),
        Viagem.status == 'Em Andamento'
    ).count() if viagens_ids else 0

    # Viagens Finalizadas (Hoje)
    viagens_finalizadas_hoje = query_tenant(Viagem).filter(
        Viagem.id.in_(viagens_ids),
        Viagem.status == 'Finalizada',
        func.date(Viagem.data_finalizacao) == hoje
    ).count() if viagens_ids else 0

    # ========== KPIs DE RECURSOS ==========
    
    # Total de Colaboradores (todos do banco tenant)
    total_colaboradores = query_tenant(Colaborador).count()

    # Motoristas Ativos (status = 'Disponível' ou 'Ocupado')
    motoristas_ativos = query_tenant(Motorista).filter(
        Motorista.status.in_(['Disponível', 'Ocupado'])
    ).count()

    # Canceladas Hoje
    canceladas_hoje = query_tenant(Solicitacao).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Cancelada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    return render_template(
        'supervisor/dashboard_supervisor.html',
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
        canceladas_hoje=canceladas_hoje
    )


@supervisor_bp.route('/cancelar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def cancelar_solicitacao(solicitacao_id):
    # ... (código de verificação de permissão) ...
    solicitacao = get_or_404_tenant(Solicitacao, solicitacao_id)
    supervisor_profile = current_user.supervisor
    # ... (outras verificações) ...

    # --- LÓGICA DA JANELA DE CORTESIA ---
    # Se a solicitação já foi agendada (tem uma viagem)
    if solicitacao.status == 'Agendada' and solicitacao.viagem:
        # Busca a configuração do tempo de cortesia no banco
        config_cortesia = Configuracao.query.filter_by(
            chave='TEMPO_CORTESIA_MINUTOS').first()
        minutos_cortesia = int(
            config_cortesia.valor) if config_cortesia else 3  # Padrão de 3 min

        # Calcula o tempo limite para o cancelamento
        limite_cancelamento = solicitacao.viagem.data_inicio + \
            timedelta(minutes=minutos_cortesia)

        # Verifica se o tempo atual já passou do limite
        if datetime.utcnow() > limite_cancelamento:
            flash(
                f'O tempo de cortesia de {minutos_cortesia} minutos para cancelar expirou. Contate o administrador.', 'danger')
            return redirect(url_for('supervisor.dashboard_supervisor'))

    # Se a solicitação ainda está pendente, ou se está agendada mas dentro da janela, permite o cancelamento.
    # Se a viagem existir, precisamos resetar o motorista e a viagem.
    if solicitacao.viagem:
        viagem = solicitacao.viagem
        # Se esta era a única solicitação na viagem, a viagem inteira é cancelada.
        if len(viagem.solicitacoes) == 1:
            viagem.motorista.status = 'Disponível'
            db.session.delete(viagem)
        # Se havia outras, a solicitação é apenas removida da viagem.
        else:
            solicitacao.viagem_id = None

    solicitacao.status = 'Cancelada'
    db.session.commit()

    flash(
        f'A solicitação para o colaborador "{solicitacao.colaborador.nome}" foi cancelada com sucesso.', 'success')
    return redirect(url_for('supervisor.dashboard_supervisor'))
