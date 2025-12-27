"""
Dashboard - KPIs Operacionais
=============================

KPIs da aba Operacional:
- KPIs de Solicitações (Pendentes, Agrupadas, Finalizadas, Canceladas)
- KPIs de Viagens (Pendentes, Agendadas, Em Andamento, Finalizadas, Canceladas)
- KPIs de Motoristas (Disponíveis, Agendados, Ocupados, Offline)
- KPIs Gerais (Total Empresas, Plantas, Motoristas, Colaboradores)

Permissões: Admin e Operador
"""

from sqlalchemy import func

from app import db
from app.models import (
    Empresa, Planta, Motorista, Colaborador, 
    Solicitacao, Viagem
)
from .dash_utils import pode_ver_kpi


def get_kpis_solicitacoes(empresa_id, data_inicio, data_fim):
    """
    Calcula os KPIs de Solicitações.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: KPIs de solicitações ou None se sem permissão
    """
    if not pode_ver_kpi('kpis_solicitacoes'):
        return None
    
    # Otimização: Consolida COUNTs em 1 query usando GROUP BY
    counts_solicitacoes = db.session.query(
        Solicitacao.status,
        func.count(Solicitacao.id)
    ).filter(
        Solicitacao.empresa_id == empresa_id
    ).group_by(Solicitacao.status).all()

    # Converte para dicionário
    kpis_dict = {status: count for status, count in counts_solicitacoes}
    kpis_dict.setdefault('Pendente', 0)
    kpis_dict.setdefault('Agrupada', 0)
    kpis_dict.setdefault('Finalizada', 0)
    kpis_dict.setdefault('Cancelada', 0)

    # Renomeia chaves para lowercase
    kpis_solicitacoes = {
        'pendentes': kpis_dict.get('Pendente', 0),
        'agrupadas': kpis_dict.get('Agrupada', 0),
        'finalizadas': kpis_dict.get('Finalizada', 0),
        'canceladas': kpis_dict.get('Cancelada', 0)
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

    return kpis_solicitacoes


def get_kpis_viagens(empresa_id, data_inicio, data_fim):
    """
    Calcula os KPIs de Viagens.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: KPIs de viagens ou None se sem permissão
    """
    if not pode_ver_kpi('kpis_viagens'):
        return None
    
    # Otimização: Consolida COUNTs em 1 query usando GROUP BY
    counts_viagens = db.session.query(
        Viagem.status,
        func.count(Viagem.id)
    ).filter(
        Viagem.empresa_id == empresa_id
    ).group_by(Viagem.status).all()

    # Converte para dicionário
    kpis_dict = {status: count for status, count in counts_viagens}
    kpis_dict.setdefault('Pendente', 0)
    kpis_dict.setdefault('Agendada', 0)
    kpis_dict.setdefault('Em Andamento', 0)
    kpis_dict.setdefault('Finalizada', 0)
    kpis_dict.setdefault('Cancelada', 0)

    # Renomeia chaves para lowercase
    kpis_viagens = {
        'pendentes': kpis_dict.get('Pendente', 0),
        'agendadas': kpis_dict.get('Agendada', 0),
        'em_andamento': kpis_dict.get('Em Andamento', 0),
        'finalizadas_total': kpis_dict.get('Finalizada', 0),
        'canceladas_total': kpis_dict.get('Cancelada', 0)
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

    return kpis_viagens


def get_kpis_motoristas():
    """
    Calcula os KPIs de Motoristas.
    Nota: Sem filtro de data, pois é status atual em tempo real.
    
    Returns:
        dict: KPIs de motoristas ou None se sem permissão
    """
    if not pode_ver_kpi('kpis_motoristas'):
        return None
    
    # Busca TODOS os motoristas ativos (independente de terem viagens)
    motoristas_empresa = Motorista.query.filter_by(status='Ativo').all()

    kpis_motoristas = {
        'disponiveis': 0,
        'agendados': 0,
        'ocupados': 0,
        'offline': 0,
        'total': len(motoristas_empresa)
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

    return kpis_motoristas


def get_kpis_gerais(empresa_id):
    """
    Calcula os KPIs Gerais (totais).
    
    Args:
        empresa_id: ID da empresa para filtrar plantas e colaboradores
        
    Returns:
        dict: KPIs gerais ou None se sem permissão
    """
    if not pode_ver_kpi('kpis_gerais'):
        return None
    
    # Total de motoristas ativos
    total_motoristas = Motorista.query.filter_by(status='Ativo').count()
    
    kpis_gerais = {
        'total_empresas': Empresa.query.count(),
        'total_plantas': Planta.query.filter_by(empresa_id=empresa_id).count(),
        'total_motoristas': total_motoristas,
        'total_colaboradores': Colaborador.query.join(Planta).filter(
            Planta.empresa_id == empresa_id
        ).count()
    }

    return kpis_gerais


def get_todos_kpis_operacionais(empresa_id, data_inicio, data_fim):
    """
    Retorna todos os KPIs da aba Operacional em um único dicionário.
    Útil para chamar uma única vez na rota principal.
    
    Args:
        empresa_id: ID da empresa para filtrar
        data_inicio: Data inicial do período
        data_fim: Data final do período
        
    Returns:
        dict: Todos os KPIs operacionais
    """
    return {
        'solicitacoes': get_kpis_solicitacoes(empresa_id, data_inicio, data_fim),
        'viagens': get_kpis_viagens(empresa_id, data_inicio, data_fim),
        'motoristas': get_kpis_motoristas(),
        'gerais': get_kpis_gerais(empresa_id)
    }
