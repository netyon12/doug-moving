"""
Dashboard - Dados para Gráficos
===============================

Dados da aba Gráficos:
- Receita Diária (Admin)
- Viagens por Horário (Admin e Operador)
- Viagens por Planta (Admin e Operador)
- Ranking de Motoristas (Admin e Operador)

Permissões: Admin e Operador (configurável por gráfico)
"""

from datetime import timedelta
from sqlalchemy import func

from app import db
from app.models import Viagem, Motorista, Planta
from .dash_utils import pode_ver_kpi
from app.config.tenant_utils import query_tenant, get_tenant_session


def get_grafico_receita_diaria(empresa_id, data_inicio, data_fim):
    """
    Calcula os dados para o gráfico de Receita Diária com total e média.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Dados do gráfico (labels, valores, total, média) ou None se sem permissão
    """
    if not pode_ver_kpi('grafico_receita_diaria'):
        return None
    
    receita_diaria = []
    labels_dias = []
    data_atual = data_inicio
    
    while data_atual <= data_fim:
        data_fim_dia = data_atual.replace(hour=23, minute=59, second=59)
        
        receita_dia = get_tenant_session().query(func.sum(Viagem.valor)).filter(
            Viagem.empresa_id == empresa_id,
            Viagem.status == 'Finalizada',
            Viagem.data_finalizacao >= data_atual,
            Viagem.data_finalizacao <= data_fim_dia
        ).scalar() or 0

        receita_diaria.append(float(receita_dia))
        labels_dias.append(data_atual.strftime('%d/%m'))
        data_atual += timedelta(days=1)
    
    # Calcular total e média
    total_receita = sum(receita_diaria)
    media_receita = total_receita / len(receita_diaria) if len(receita_diaria) > 0 else 0
    
    return {
        'labels_dias': labels_dias,
        'receita_diaria': receita_diaria,
        'total': total_receita,
        'media': media_receita
    }


def get_grafico_viagens_horario(empresa_id, data_inicio, data_fim):
    """
    Calcula os dados para o gráfico de Viagens por Horário (Entrada, Saída, Desligamento).
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Dados do gráfico com 3 séries (entrada, saída, desligamento) ou None se sem permissão
    """
    if not pode_ver_kpi('grafico_viagens_horario'):
        return None
    
    # Busca todas as viagens finalizadas no período
    viagens_finalizadas = query_tenant(Viagem).filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).all()
    
    # Agrupa por hora (0-23) para cada tipo de horário
    entrada_por_hora = {h: 0 for h in range(24)}
    saida_por_hora = {h: 0 for h in range(24)}
    desligamento_por_hora = {h: 0 for h in range(24)}
    
    for viagem in viagens_finalizadas:
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
    
    return {
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


def get_grafico_viagens_planta(empresa_id, data_inicio, data_fim):
    """
    Calcula os dados para o gráfico de Viagens por Planta (Pizza).
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Dados do gráfico (labels, valores, percentuais) ou None se sem permissão
    """
    if not pode_ver_kpi('grafico_viagens_planta'):
        return None
    
    # Busca viagens agrupadas por planta
    viagens_por_planta = get_tenant_session().query(
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
    
    total_viagens = sum([p.total_viagens for p in viagens_por_planta])
    
    return {
        'labels': [p.nome for p in viagens_por_planta],
        'valores': [p.total_viagens for p in viagens_por_planta],
        'percentuais': [
            round((p.total_viagens / total_viagens * 100), 1) if total_viagens > 0 else 0 
            for p in viagens_por_planta
        ]
    }


def get_grafico_ranking_motoristas(empresa_id, data_inicio, data_fim):
    """
    Calcula os dados para o Ranking Completo de Motoristas.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Dados do ranking (motoristas, viagens) ou None se sem permissão
    """
    if not pode_ver_kpi('grafico_ranking_motoristas'):
        return None
    
    # Busca ranking de motoristas
    ranking_motoristas = get_tenant_session().query(
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
    
    return {
        'motoristas': [r.nome for r in ranking_motoristas],
        'viagens': [r.total_viagens for r in ranking_motoristas]
    }


def get_todos_graficos(empresa_id, data_inicio, data_fim, kpis_viagens=None):
    """
    Retorna todos os dados de gráficos em um único dicionário.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        kpis_viagens: KPIs de viagens (não usado mais, mantido para compatibilidade)
        
    Returns:
        dict: Todos os dados de gráficos (apenas os que o usuário tem permissão)
    """
    graficos = {}
    
    # Gráfico 1: Receita Diária (Admin)
    receita = get_grafico_receita_diaria(empresa_id, data_inicio, data_fim)
    if receita:
        graficos['receita'] = receita
    
    # Gráfico 2: Viagens por Horário (Admin e Operador)
    viagens_horario = get_grafico_viagens_horario(empresa_id, data_inicio, data_fim)
    if viagens_horario:
        graficos['viagens_horario'] = viagens_horario
    
    # Gráfico 3: Viagens por Planta (Admin e Operador)
    viagens_planta = get_grafico_viagens_planta(empresa_id, data_inicio, data_fim)
    if viagens_planta:
        graficos['viagens_planta'] = viagens_planta
    
    # Gráfico 4: Ranking de Motoristas (Admin e Operador)
    ranking_motoristas = get_grafico_ranking_motoristas(empresa_id, data_inicio, data_fim)
    if ranking_motoristas:
        graficos['ranking_motoristas'] = ranking_motoristas
    
    return graficos if graficos else None
