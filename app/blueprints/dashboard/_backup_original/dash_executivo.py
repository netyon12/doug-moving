"""
Dashboard - KPIs Executivos
===========================

KPIs da aba Executivo:
- Receita Total (apenas Admin)
- Custo de Repasse (apenas Admin)
- Margem Líquida (apenas Admin)
- Ticket Médio (apenas Admin)
- Comparação com Período Anterior (apenas Admin)
- Taxa de Ocupação (Admin e Operador)
- Tempo Médio de Viagem (Admin e Operador)
- Viagens por Motorista (Admin e Operador)
- Taxa de Cancelamento (Admin e Operador)

Permissões: Variável por KPI
"""

from datetime import timedelta
from sqlalchemy import func

from app import db
from app.models import Viagem, Solicitacao
from .dash_utils import pode_ver_kpi, get_capacidade_veiculo


def get_viagens_finalizadas_periodo(empresa_id, data_inicio, data_fim):
    """
    Busca as viagens finalizadas no período.
    Função auxiliar usada por vários KPIs.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        list: Lista de viagens finalizadas
    """
    return Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio,
        Viagem.data_finalizacao <= data_fim
    ).all()


def get_kpis_financeiros(empresa_id, data_inicio, data_fim, viagens_finalizadas=None):
    """
    Calcula os KPIs financeiros (apenas Admin).
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        viagens_finalizadas: Lista de viagens (opcional, para evitar query duplicada)
        
    Returns:
        dict: KPIs financeiros ou None se sem permissão
    """
    # Verifica permissão para qualquer KPI financeiro
    tem_permissao_financeiro = (
        pode_ver_kpi('receita_total') or 
        pode_ver_kpi('custo_repasse') or 
        pode_ver_kpi('margem_liquida') or 
        pode_ver_kpi('ticket_medio')
    )
    
    if not tem_permissao_financeiro:
        return None
    
    # Busca viagens se não foram passadas
    if viagens_finalizadas is None:
        viagens_finalizadas = get_viagens_finalizadas_periodo(empresa_id, data_inicio, data_fim)
    
    num_viagens = len(viagens_finalizadas)
    
    kpis = {}
    
    # Receita Total
    if pode_ver_kpi('receita_total'):
        receita_total = sum([v.valor for v in viagens_finalizadas if v.valor]) or 0
        kpis['receita_total'] = float(receita_total)
    
    # Custo de Repasse
    if pode_ver_kpi('custo_repasse'):
        custo_repasse = sum([v.valor_repasse for v in viagens_finalizadas if v.valor_repasse]) or 0
        kpis['custo_repasse'] = float(custo_repasse)
    
    # Margem Líquida
    if pode_ver_kpi('margem_liquida'):
        receita = kpis.get('receita_total', sum([v.valor for v in viagens_finalizadas if v.valor]) or 0)
        custo = kpis.get('custo_repasse', sum([v.valor_repasse for v in viagens_finalizadas if v.valor_repasse]) or 0)
        kpis['margem_liquida'] = float(receita - custo)
    
    # Ticket Médio
    if pode_ver_kpi('ticket_medio'):
        receita = kpis.get('receita_total', sum([v.valor for v in viagens_finalizadas if v.valor]) or 0)
        kpis['ticket_medio'] = round(receita / num_viagens, 2) if num_viagens > 0 else 0
    
    return kpis if kpis else None


def get_kpis_operacionais_executivo(empresa_id, data_inicio, data_fim, viagens_finalizadas=None):
    """
    Calcula os KPIs operacionais da aba Executivo (Admin e Operador).
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        viagens_finalizadas: Lista de viagens (opcional, para evitar query duplicada)
        
    Returns:
        dict: KPIs operacionais ou None se sem permissão
    """
    # Verifica permissão para qualquer KPI operacional
    tem_permissao = (
        pode_ver_kpi('taxa_ocupacao') or 
        pode_ver_kpi('tempo_medio_viagem') or 
        pode_ver_kpi('viagens_por_motorista') or 
        pode_ver_kpi('taxa_cancelamento')
    )
    
    if not tem_permissao:
        return None
    
    # Busca viagens se não foram passadas
    if viagens_finalizadas is None:
        viagens_finalizadas = get_viagens_finalizadas_periodo(empresa_id, data_inicio, data_fim)
    
    num_viagens = len(viagens_finalizadas)
    capacidade_veiculo = get_capacidade_veiculo()
    
    kpis = {}
    
    # Taxa de Ocupação
    if pode_ver_kpi('taxa_ocupacao'):
        total_passageiros = 0
        for viagem in viagens_finalizadas:
            passageiros_viagem = Solicitacao.query.filter_by(viagem_id=viagem.id).count()
            total_passageiros += passageiros_viagem
        
        if num_viagens > 0:
            taxa_ocupacao = (total_passageiros / (num_viagens * capacidade_veiculo)) * 100
        else:
            taxa_ocupacao = 0
        
        kpis['taxa_ocupacao'] = round(taxa_ocupacao, 1)
        kpis['total_passageiros'] = total_passageiros
        kpis['capacidade_veiculo'] = capacidade_veiculo
        kpis['num_viagens_finalizadas'] = num_viagens
    
    # Tempo Médio de Viagem
    if pode_ver_kpi('tempo_medio_viagem'):
        viagens_com_tempo = [v for v in viagens_finalizadas if v.data_inicio and v.data_finalizacao]
        
        if viagens_com_tempo:
            tempos = []
            for viagem in viagens_com_tempo:
                duracao = (viagem.data_finalizacao - viagem.data_inicio).total_seconds() / 60
                tempos.append(duracao)
            tempo_medio = sum(tempos) / len(tempos)
        else:
            tempo_medio = 0
        
        kpis['tempo_medio_viagem'] = round(tempo_medio, 1)
    
    # Viagens por Motorista
    if pode_ver_kpi('viagens_por_motorista'):
        motoristas_ativos = db.session.query(Viagem.motorista_id).filter(
            Viagem.empresa_id == empresa_id,
            Viagem.status == 'Finalizada',
            Viagem.data_finalizacao >= data_inicio,
            Viagem.data_finalizacao <= data_fim,
            Viagem.motorista_id.isnot(None)
        ).distinct().count()
        
        viagens_por_motorista = (num_viagens / motoristas_ativos) if motoristas_ativos > 0 else 0
        kpis['viagens_por_motorista'] = round(viagens_por_motorista, 1)
    
    # Taxa de Cancelamento
    if pode_ver_kpi('taxa_cancelamento'):
        viagens_canceladas = Viagem.query.filter(
            Viagem.empresa_id == empresa_id,
            Viagem.status == 'Cancelada',
            Viagem.data_criacao >= data_inicio,
            Viagem.data_criacao <= data_fim
        ).count()
        
        total_viagens_periodo = num_viagens + viagens_canceladas
        taxa_cancelamento = (viagens_canceladas / total_viagens_periodo * 100) if total_viagens_periodo > 0 else 0
        kpis['taxa_cancelamento'] = round(taxa_cancelamento, 1)
    
    return kpis if kpis else None


def get_comparacao_periodo(empresa_id, data_inicio, data_fim, viagens_finalizadas=None):
    """
    Calcula a comparação com o período anterior (apenas Admin).
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        viagens_finalizadas: Lista de viagens do período atual (opcional)
        
    Returns:
        dict: Variações percentuais ou None se sem permissão
    """
    if not pode_ver_kpi('comparacao_periodo'):
        return None
    
    # Busca viagens do período atual se não foram passadas
    if viagens_finalizadas is None:
        viagens_finalizadas = get_viagens_finalizadas_periodo(empresa_id, data_inicio, data_fim)
    
    # Calcula período anterior
    dias_periodo = (data_fim - data_inicio).days + 1
    data_inicio_anterior = data_inicio - timedelta(days=dias_periodo)
    data_fim_anterior = data_inicio - timedelta(days=1)
    
    # Busca viagens do período anterior
    viagens_anterior = Viagem.query.filter(
        Viagem.empresa_id == empresa_id,
        Viagem.status == 'Finalizada',
        Viagem.data_finalizacao >= data_inicio_anterior,
        Viagem.data_finalizacao <= data_fim_anterior
    ).all()
    
    # Métricas do período atual
    receita_atual = sum([v.valor for v in viagens_finalizadas if v.valor]) or 0
    margem_atual = sum([(v.valor or 0) - (v.valor_repasse or 0) for v in viagens_finalizadas]) or 0
    num_viagens_atual = len(viagens_finalizadas)
    
    # Métricas do período anterior
    receita_anterior = sum([v.valor for v in viagens_anterior if v.valor]) or 0
    margem_anterior = sum([(v.valor or 0) - (v.valor_repasse or 0) for v in viagens_anterior]) or 0
    num_viagens_anterior = len(viagens_anterior)
    
    # Calcular variações percentuais
    variacao_receita = ((receita_atual - receita_anterior) / receita_anterior * 100) if receita_anterior > 0 else 0
    variacao_margem = ((margem_atual - margem_anterior) / margem_anterior * 100) if margem_anterior > 0 else 0
    variacao_viagens = ((num_viagens_atual - num_viagens_anterior) / num_viagens_anterior * 100) if num_viagens_anterior > 0 else 0
    
    return {
        'variacao_receita': round(variacao_receita, 1),
        'variacao_margem': round(variacao_margem, 1),
        'variacao_viagens': round(variacao_viagens, 1)
    }


def get_todos_kpis_executivos(empresa_id, data_inicio, data_fim):
    """
    Retorna todos os KPIs da aba Executivo em um único dicionário.
    Otimizado para fazer apenas uma query de viagens.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Todos os KPIs executivos (apenas os que o usuário tem permissão)
    """
    # Busca viagens uma única vez
    viagens_finalizadas = get_viagens_finalizadas_periodo(empresa_id, data_inicio, data_fim)
    
    # Coleta todos os KPIs
    kpis_financeiros = get_kpis_financeiros(empresa_id, data_inicio, data_fim, viagens_finalizadas)
    kpis_operacionais = get_kpis_operacionais_executivo(empresa_id, data_inicio, data_fim, viagens_finalizadas)
    comparacao = get_comparacao_periodo(empresa_id, data_inicio, data_fim, viagens_finalizadas)
    
    # Monta dicionário final
    resultado = {}
    
    if kpis_financeiros:
        resultado.update(kpis_financeiros)
    
    if kpis_operacionais:
        resultado.update(kpis_operacionais)
    
    if comparacao:
        resultado.update(comparacao)
    
    return resultado if resultado else None
