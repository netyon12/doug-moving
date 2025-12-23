"""
Dashboard - Utilitários e Controle de Permissões
================================================

Funções auxiliares e controle granular de permissões para o dashboard.
"""

from datetime import datetime
import calendar
from flask import request
from flask_login import current_user

from app.models import Empresa, Configuracao


# =============================================================================
# CONTROLE DE PERMISSÕES
# =============================================================================

# Permissões por KPI/Gráfico
# Adicione ou remova perfis conforme necessário
PERMISSOES_KPIS = {
    # =========================================================================
    # ABA OPERACIONAL - Admin e Operador veem tudo
    # =========================================================================
    'kpis_solicitacoes': ['admin', 'operador'],
    'kpis_viagens': ['admin', 'operador'],
    'kpis_motoristas': ['admin', 'operador'],
    'kpis_gerais': ['admin', 'operador'],
    
    # =========================================================================
    # ABA EXECUTIVO - KPIs Financeiros (apenas Admin)
    # =========================================================================
    'receita_total': ['admin'],
    'custo_repasse': ['admin'],
    'margem_liquida': ['admin'],
    'ticket_medio': ['admin'],
    'comparacao_periodo': ['admin'],
    
    # =========================================================================
    # ABA EXECUTIVO - KPIs Operacionais (Admin e Operador)
    # =========================================================================
    'taxa_ocupacao': ['admin', 'operador'],
    'tempo_medio_viagem': ['admin', 'operador'],
    'viagens_por_motorista': ['admin', 'operador'],
    'taxa_cancelamento': ['admin', 'operador'],
    
    # =========================================================================
    # ABA GRÁFICOS
    # =========================================================================
    'grafico_receita_diaria': ['admin'],  # Apenas Admin vê receita
    'grafico_viagens_horario': ['admin', 'operador'],
    'grafico_viagens_planta': ['admin', 'operador'],
    'grafico_ranking_motoristas': ['admin', 'operador'],
    
    # =========================================================================
    # ABAS DO DASHBOARD (controle de acesso às abas)
    # =========================================================================
    'aba_operacional': ['admin', 'operador'],
    'aba_executivo': ['admin', 'operador'],  # Operador vê a aba, mas com KPIs limitados
    'aba_graficos': ['admin', 'operador'],
}


def pode_ver_kpi(kpi_nome):
    """
    Verifica se o usuário atual pode ver determinado KPI ou gráfico.
    
    Args:
        kpi_nome: Nome do KPI conforme definido em PERMISSOES_KPIS
        
    Returns:
        bool: True se o usuário tem permissão, False caso contrário
    """
    if not current_user.is_authenticated:
        return False
    return current_user.role in PERMISSOES_KPIS.get(kpi_nome, [])


def pode_ver_aba(aba_nome):
    """
    Verifica se o usuário atual pode ver determinada aba do dashboard.
    
    Args:
        aba_nome: 'operacional', 'executivo' ou 'graficos'
        
    Returns:
        bool: True se o usuário tem permissão, False caso contrário
    """
    return pode_ver_kpi(f'aba_{aba_nome}')


def get_permissoes_usuario():
    """
    Retorna um dicionário com todas as permissões do usuário atual.
    Útil para passar ao template e controlar a exibição de elementos.
    
    Returns:
        dict: Dicionário com nome_kpi: bool
    """
    permissoes = {}
    for kpi_nome in PERMISSOES_KPIS.keys():
        permissoes[kpi_nome] = pode_ver_kpi(kpi_nome)
    return permissoes


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_filtros():
    """
    Obtém os filtros de empresa e período a partir dos parâmetros da URL.
    
    Returns:
        dict: Dicionário com empresa_id, data_inicio, data_fim, empresas, empresa_selecionada
    """
    # Obter filtro de empresa (padrão: primeira empresa ou ID 1)
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

    return {
        'empresa_id': empresa_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_inicio_str': data_inicio_str,
        'data_fim_str': data_fim_str,
        'empresas': empresas,
        'empresa_selecionada': empresa_selecionada
    }


def get_capacidade_veiculo():
    """
    Obtém a capacidade máxima de passageiros por veículo dos parâmetros gerais.
    
    Returns:
        int: Capacidade do veículo (padrão: 4)
    """
    config_capacidade = Configuracao.query.filter_by(
        chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
    return int(config_capacidade.valor) if config_capacidade else 4
