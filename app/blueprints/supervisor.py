from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta, date
from sqlalchemy import func

from .. import db
from ..models import User, Supervisor, Colaborador, Motorista, Bloco, Viagem, Solicitacao, Configuracao
from ..decorators import permission_required
from ..models import Empresa
from io import StringIO
import csv

# Cria um Blueprint específico para autenticação
supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')


# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================
# ROTAS DO SUPERVISOR 
# =============================================================================
# =============================================================================
# =============================================================================
# =============================================================================




@supervisor_bp.route('/dashboard')
@login_required
@permission_required('supervisor')
def dashboard_supervisor():
    supervisor_profile = current_user.supervisor
    if not supervisor_profile:
        flash('Perfil de supervisor não encontrado.', 'danger')
        return redirect(url_for('auth.logout'))
    
    # KPI 1: Solicitações Pendentes
    solicitacoes_pendentes = Solicitacao.query.filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Pendente'
    ).count()

    # KPI 2: Solicitações Agendadas
    solicitacoes_agendadas = Solicitacao.query.filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Agendada'
    ).count()

    # KPI 3: Viagens em Andamento (através das solicitações)
    viagens_ids = db.session.query(Solicitacao.viagem_id).filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.viagem_id.isnot(None)
    ).distinct().all()
    viagens_ids = [v[0] for v in viagens_ids]
    
    viagens_andamento = Viagem.query.filter(
        Viagem.id.in_(viagens_ids),
        Viagem.status == 'Em Andamento'
    ).count() if viagens_ids else 0

    # KPI 4: Taxa de Ocupação Média (calculada com base nas viagens)
    # KPI 4: Taxa de Ocupação Média (calculada com base nas viagens FINALIZADAS)
    # Busca capacidade dos parâmetros gerais
    config_capacidade = Configuracao.query.filter_by(chave='capacidade_veiculo').first()
    capacidade_veiculo = int(config_capacidade.valor) if config_capacidade and config_capacidade.valor else 3

    if viagens_ids:
        # Filtra apenas viagens FINALIZADAS
        viagens_finalizadas = Viagem.query.filter(
            Viagem.id.in_(viagens_ids),
            Viagem.status == 'Finalizada'
        ).all()
        
        if viagens_finalizadas:
            # Soma total de passageiros transportados
            total_passageiros = sum(viagem.quantidade_passageiros or 0 for viagem in viagens_finalizadas)
            total_viagens = len(viagens_finalizadas)
            
            # Fórmula: (Total Passageiros) / (Total Viagens × Capacidade) × 100
            taxa_ocupacao_media = (total_passageiros / (total_viagens * capacidade_veiculo)) * 100 if total_viagens > 0 else 0
        else:
            taxa_ocupacao_media = 0
    else:
        taxa_ocupacao_media = 0

    # KPI 5: Finalizadas Hoje
    hoje = date.today()
    finalizadas_hoje = Solicitacao.query.filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Finalizada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    # KPI 6: Canceladas Hoje
    canceladas_hoje = Solicitacao.query.filter(
        Solicitacao.supervisor_id == supervisor_profile.id,
        Solicitacao.status == 'Cancelada',
        func.date(Solicitacao.data_criacao) == hoje
    ).count()

    # KPI 7: Total de Supervisores (no caso do supervisor, mostra apenas 1 - ele mesmo)
    total_supervisores = 1

    # KPI 8: Total de Colaboradores da Planta
    total_colaboradores = Colaborador.query.filter_by(
        planta=supervisor_profile.planta
    ).count()

    return render_template(
        'dashboard_supervisor.html',
        solicitacoes_pendentes=solicitacoes_pendentes,
        solicitacoes_agendadas=solicitacoes_agendadas,
        viagens_andamento=viagens_andamento,
        taxa_ocupacao_media=taxa_ocupacao_media,
        finalizadas_hoje=finalizadas_hoje,
        canceladas_hoje=canceladas_hoje,
        total_supervisores=total_supervisores,
        total_colaboradores=total_colaboradores
    )









@supervisor_bp.route('/cancelar_solicitacao/<int:solicitacao_id>', methods=['POST'])
@login_required
def cancelar_solicitacao(solicitacao_id):
    # ... (código de verificação de permissão) ...
    solicitacao = Solicitacao.query.get_or_404(solicitacao_id)
    supervisor_profile = current_user.supervisor
    # ... (outras verificações) ...

    # --- LÓGICA DA JANELA DE CORTESIA ---
    # Se a solicitação já foi agendada (tem uma viagem)
    if solicitacao.status == 'Agendada' and solicitacao.viagem:
        # Busca a configuração do tempo de cortesia no banco
        config_cortesia = Configuracao.query.filter_by(chave='TEMPO_CORTESIA_MINUTOS').first()
        minutos_cortesia = int(config_cortesia.valor) if config_cortesia else 3 # Padrão de 3 min

        # Calcula o tempo limite para o cancelamento
        limite_cancelamento = solicitacao.viagem.data_inicio + timedelta(minutes=minutos_cortesia)

        # Verifica se o tempo atual já passou do limite
        if datetime.utcnow() > limite_cancelamento:
            flash(f'O tempo de cortesia de {minutos_cortesia} minutos para cancelar expirou. Contate o administrador.', 'danger')
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

    flash(f'A solicitação para o colaborador "{solicitacao.colaborador.nome}" foi cancelada com sucesso.', 'success')
    return redirect(url_for('supervisor.dashboard_supervisor'))

