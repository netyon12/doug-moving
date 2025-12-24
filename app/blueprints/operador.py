# app/blueprints/operador.py
"""
Blueprint do Operador
=====================
Dashboard operacional sem aba Executivo (sem dados financeiros).
Baseado no dashboard.py do Admin.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
import calendar

from app import db
from app.models import (
    Empresa, Planta, Motorista, Colaborador, 
    Solicitacao, Viagem
)
from app.decorators import role_required

operador_bp = Blueprint('operador', __name__, url_prefix='/operador')


@operador_bp.route('/dashboard')
@login_required
@role_required('operador')
def operador_dashboard():
    """Dashboard do Operador - sem aba Executivo (sem dados financeiros)."""
    
    # ===== FILTROS =====
    # Obter filtro de empresa (padrão: primeira empresa)
    empresa_id = request.args.get('empresa_id', type=int)
    if not empresa_id:
        primeira_empresa = Empresa.query.order_by(Empresa.id).first()
        empresa_id = primeira_empresa.id if primeira_empresa else 1

    # Obter filtro de período (padrão: mês atual)
    hoje = datetime.now()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    ultimo_dia_mes = datetime(hoje.year, hoje.month, calendar.monthrange(
        hoje.year, hoje.month)[1], 23, 59, 59)

    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
    else:
        data_inicio = primeiro_dia_mes
        data_inicio_str = data_inicio.strftime('%Y-%m-%d')

    if data_fim_str:
        data_fim = datetime.strptime(
            data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        data_fim = ultimo_dia_mes
        data_fim_str = data_fim.strftime('%Y-%m-%d')

    # Buscar todas as empresas para o dropdown
    empresas = Empresa.query.order_by(Empresa.nome).all()
    empresa_selecionada = Empresa.query.get(empresa_id)

    # ===== KPIs DE SOLICITAÇÕES =====
    # Otimização: Consolida COUNTs em 1 query usando GROUP BY
    counts_solicitacoes = db.session.query(
        Solicitacao.status,
        func.count(Solicitacao.id)
    ).filter(
        Solicitacao.empresa_id == empresa_id
    ).group_by(Solicitacao.status).all()

    # Converte para dicionário
    kpis_solicitacoes_dict = {status: count for status, count in counts_solicitacoes}
    kpis_solicitacoes_dict.setdefault('Pendente', 0)
    kpis_solicitacoes_dict.setdefault('Agrupada', 0)
    kpis_solicitacoes_dict.setdefault('Finalizada', 0)
    kpis_solicitacoes_dict.setdefault('Cancelada', 0)

    # Renomeia chaves para lowercase
    kpis_solicitacoes = {
        'pendentes': kpis_solicitacoes_dict.get('Pendente', 0),
        'agrupadas': kpis_solicitacoes_dict.get('Agrupada', 0),
        'finalizadas': kpis_solicitacoes_dict.get('Finalizada', 0),
        'canceladas': kpis_solicitacoes_dict.get('Cancelada', 0)
    }

    # Finalizadas e Canceladas do período (queries separadas necessárias)
    kpis_solicitacoes['finalizadas_periodo'] = Solicitacao.query.filter(
        Solicitacao.empresa_id == empresa_id,
        Solicitacao.status == 'Finalizada',
        Solicitacao.data_atualizacao >= data_inicio,
        Solicitacao.data_atualizacao <= data_fim
    ).count()
    kpis_solicitacoes['canceladas_periodo'] = Solicitacao.query.filter(
        Solicitacao.empresa_id == empresa_id,
        Solicitacao.status == 'Cancelada',
        Solicitacao.data_atualizacao >= data_inicio,
        Solicitacao.data_atualizacao <= data_fim
    ).count()

    # ===== KPIs DE VIAGENS =====
    # Otimização: Consolida COUNTs em 1 query usando GROUP BY
    counts_viagens = db.session.query(
        Viagem.status,
        func.count(Viagem.id)
    ).filter(
        Viagem.empresa_id == empresa_id
    ).group_by(Viagem.status).all()

    # Converte para dicionário
    kpis_viagens_dict = {status: count for status, count in counts_viagens}
    kpis_viagens_dict.setdefault('Pendente', 0)
    kpis_viagens_dict.setdefault('Agendada', 0)
    kpis_viagens_dict.setdefault('Em Andamento', 0)
    kpis_viagens_dict.setdefault('Finalizada', 0)
    kpis_viagens_dict.setdefault('Cancelada', 0)

    # Renomeia chaves para lowercase
    kpis_viagens = {
        'pendentes': kpis_viagens_dict.get('Pendente', 0),
        'agendadas': kpis_viagens_dict.get('Agendada', 0),
        'em_andamento': kpis_viagens_dict.get('Em Andamento', 0),
        'finalizadas_total': kpis_viagens_dict.get('Finalizada', 0),
        'canceladas_total': kpis_viagens_dict.get('Cancelada', 0)
    }

    # Viagens finalizadas e canceladas DO PERÍODO (queries separadas necessárias)
    kpis_viagens['finalizadas_periodo'] = Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).count()

    kpis_viagens['canceladas_periodo'] = Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Cancelada',
        Viagem.data_criacao >= data_inicio,
        Viagem.data_criacao <= data_fim
    ).count()

    # ===== KPIs DE MOTORISTAS (SEM FILTRO DE DATA) =====
    # Busca TODOS os motoristas ativos (independente de terem viagens)
    motoristas_empresa = Motorista.query.filter_by(status='Ativo').all()

    kpis_motoristas = {
        'disponiveis': 0,
        'agendados': 0,
        'ocupados': 0,
        'offline': 0
    }

    for motorista in motoristas_empresa:
        status_atual = motorista.get_status_atual()

        # Disponíveis = disponivel + agendado (conforme regra de negócio)
        if status_atual in ['disponivel', 'agendado']:
            kpis_motoristas['disponiveis'] += 1

        # Contadores específicos
        if status_atual == 'agendado':
            kpis_motoristas['agendados'] += 1
        elif status_atual == 'ocupado':
            kpis_motoristas['ocupados'] += 1
        elif status_atual == 'offline':
            kpis_motoristas['offline'] += 1

    # ===== DADOS GERAIS =====
    kpis_gerais = {
        'total_empresas': Empresa.query.count(),
        'total_plantas': Planta.query.filter_by(empresa_id=empresa_id).count(),
        'total_motoristas': len(motoristas_empresa),
        'total_colaboradores': Colaborador.query.join(Planta).filter(Planta.empresa_id == empresa_id).count()
    }

    # ===== KPIs DE PERFORMANCE (apenas os permitidos para Operador) =====
    # Calcular métricas operacionais (sem dados financeiros)
    
    # Taxa de Ocupação: % de motoristas ocupados em relação ao total ativo
    total_motoristas_ativos = len(motoristas_empresa)
    taxa_ocupacao = round((kpis_motoristas['ocupados'] / total_motoristas_ativos * 100), 1) if total_motoristas_ativos > 0 else 0
    
    # Tempo Médio de Viagem (em minutos) - baseado nas viagens finalizadas do período
    viagens_finalizadas = Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim,
        Viagem.data_inicio.isnot(None),
        Viagem.data_finalizacao.isnot(None)
    ).all()
    
    if viagens_finalizadas:
        tempos = []
        for v in viagens_finalizadas:
            if v.data_inicio and v.data_finalizacao:
                duracao = (v.data_finalizacao - v.data_inicio).total_seconds() / 60
                if duracao > 0:
                    tempos.append(duracao)
        tempo_medio_viagem = round(sum(tempos) / len(tempos), 0) if tempos else 0
    else:
        tempo_medio_viagem = 0
    
    # Viagens por Motorista (média no período)
    viagens_por_motorista = round(kpis_viagens['finalizadas_periodo'] / total_motoristas_ativos, 1) if total_motoristas_ativos > 0 else 0
    
    # Taxa de Cancelamento
    total_viagens_periodo = kpis_viagens['finalizadas_periodo'] + kpis_viagens['canceladas_periodo']
    taxa_cancelamento = round((kpis_viagens['canceladas_periodo'] / total_viagens_periodo * 100), 1) if total_viagens_periodo > 0 else 0
    
    kpis_performance = {
        'taxa_ocupacao': taxa_ocupacao,
        'tempo_medio_viagem': int(tempo_medio_viagem),
        'viagens_por_motorista': viagens_por_motorista,
        'taxa_cancelamento': taxa_cancelamento
    }

    # ===== DADOS PARA GRÁFICOS =====
    
    # Gráfico 1: Viagens por Horário (Entrada, Saída, Desligamento)
    viagens_finalizadas_horario = Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).all()
    
    # Agrupa por hora (0-23) para cada tipo de horário
    entrada_por_hora = {h: 0 for h in range(24)}
    saida_por_hora = {h: 0 for h in range(24)}
    desligamento_por_hora = {h: 0 for h in range(24)}
    
    for viagem in viagens_finalizadas_horario:
        # Horário de entrada
        if viagem.horario_entrada:
            hora = viagem.horario_entrada.hour
            entrada_por_hora[hora] += 1
        
        # Horário de saída
        if viagem.horario_saida:
            hora = viagem.horario_saida.hour
            saida_por_hora[hora] += 1
        
        # Horário de desligamento
        if viagem.horario_desligamento:
            hora = viagem.horario_desligamento.hour
            desligamento_por_hora[hora] += 1
    
    # Calcula totais
    total_entrada = sum(entrada_por_hora.values())
    total_saida = sum(saida_por_hora.values())
    total_desligamento = sum(desligamento_por_hora.values())
    total_geral = total_entrada + total_saida + total_desligamento
    
    grafico_viagens_horario = {
        'labels': [f'{h:02d}:00' for h in range(24)],
        'series': [
            {
                'name': 'Entrada',
                'data': [entrada_por_hora[h] for h in range(24)],
                'color': '#4CAF50',  # Verde
                'total': total_entrada
            },
            {
                'name': 'Saída',
                'data': [saida_por_hora[h] for h in range(24)],
                'color': '#2196F3',  # Azul
                'total': total_saida
            },
            {
                'name': 'Desligamento',
                'data': [desligamento_por_hora[h] for h in range(24)],
                'color': '#FF9800',  # Laranja
                'total': total_desligamento
            }
        ],
        'total': total_geral
    }
    
    # Gráfico 2: Ranking Completo de Motoristas
    ranking_motoristas = db.session.query(
        Motorista.nome,
        func.count(Viagem.id).label('total_viagens')
    ).join(
        Viagem, Viagem.motorista_id == Motorista.id
    ).filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).group_by(
        Motorista.id, Motorista.nome
    ).order_by(
        func.count(Viagem.id).desc()
    ).all()
    
    grafico_ranking_motoristas = {
        'motoristas': [r.nome for r in ranking_motoristas],
        'viagens': [r.total_viagens for r in ranking_motoristas]
    }
    
    # Gráfico 3: Viagens por Planta (Pizza)
    viagens_por_planta = db.session.query(
        Planta.nome,
        func.count(Viagem.id).label('total_viagens')
    ).join(
        Viagem, Viagem.planta_id == Planta.id
    ).filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).group_by(
        Planta.id, Planta.nome
    ).order_by(
        func.count(Viagem.id).desc()
    ).all()
    
    total_viagens_plantas = sum([p.total_viagens for p in viagens_por_planta])
    
    grafico_viagens_planta = {
        'labels': [p.nome for p in viagens_por_planta],
        'valores': [p.total_viagens for p in viagens_por_planta],
        'percentuais': [round((p.total_viagens / total_viagens_plantas * 100), 1) if total_viagens_plantas > 0 else 0 for p in viagens_por_planta]
    }
    
    dados_graficos = {
        'viagens_horario': grafico_viagens_horario,
        'ranking_motoristas': grafico_ranking_motoristas,
        'viagens_planta': grafico_viagens_planta
    }

    return render_template(
        'operador/dashboard_operador.html',
        aba_ativa='dashboard',
        empresas=empresas,
        empresa_selecionada=empresa_selecionada,
        kpis_solicitacoes=kpis_solicitacoes,
        kpis_viagens=kpis_viagens,
        kpis_motoristas=kpis_motoristas,
        kpis_gerais=kpis_gerais,
        kpis_performance=kpis_performance,
        dados_graficos=dados_graficos,
        data_inicio=data_inicio_str,
        data_fim=data_fim_str
    )
