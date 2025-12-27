"""
Dashboard Module
================

Módulo reorganizado do dashboard com separação por responsabilidade:

- dash_utils.py: Funções auxiliares e controle de permissões
- dash_operacional.py: KPIs da aba Operacional
- dash_executivo.py: KPIs da aba Executivo
- dash_graficos.py: Dados para gráficos
- dashboard.py: Rota principal

Uso:
----
Este módulo é importado automaticamente pelo blueprint admin.
Não é necessário registrar separadamente.

Para adicionar novos KPIs ou gráficos:
1. Adicione a permissão em PERMISSOES_KPIS (dash_utils.py)
2. Implemente a função no arquivo correspondente
3. Chame a função em dashboard.py
4. Adicione a verificação no template

Exemplo de adição de novo gráfico:
----------------------------------
# Em dash_utils.py:
PERMISSOES_KPIS = {
    ...
    'grafico_novo': ['admin'],  # Apenas admin pode ver
}

# Em dash_graficos.py:
def get_grafico_novo(empresa_id, data_inicio, data_fim):
    if not pode_ver_kpi('grafico_novo'):
        return None
    # Implementar lógica
    return {'labels': [...], 'valores': [...]}

# Em dashboard.py:
from .dash_graficos import get_grafico_novo
# Chamar a função e passar para o template

# No template:
{% if permissoes.grafico_novo %}
    <!-- Exibir gráfico -->
{% endif %}
"""

# Importa a rota principal para que seja registrada no blueprint admin
from .dashboard import admin_dashboard

# Exporta funções úteis para uso externo (se necessário)
from .dash_utils import (
    pode_ver_kpi,
    pode_ver_aba,
    get_permissoes_usuario,
    get_filtros,
    get_capacidade_veiculo,
    PERMISSOES_KPIS
)

from .dash_operacional import (
    get_kpis_solicitacoes,
    get_kpis_viagens,
    get_kpis_motoristas,
    get_kpis_gerais,
    get_todos_kpis_operacionais
)

from .dash_executivo import (
    get_kpis_financeiros,
    get_kpis_operacionais_executivo,
    get_comparacao_periodo,
    get_todos_kpis_executivos
)

from .dash_graficos import (
    get_grafico_receita_diaria,
    get_grafico_viagens_horario,
    get_grafico_viagens_planta,
    get_grafico_ranking_motoristas,
    get_todos_graficos
)

__all__ = [
    # Rota
    'admin_dashboard',
    
    # Permissões
    'pode_ver_kpi',
    'pode_ver_aba',
    'get_permissoes_usuario',
    'PERMISSOES_KPIS',
    
    # Utilitários
    'get_filtros',
    'get_capacidade_veiculo',
    
    # KPIs Operacionais
    'get_kpis_solicitacoes',
    'get_kpis_viagens',
    'get_kpis_motoristas',
    'get_kpis_gerais',
    'get_todos_kpis_operacionais',
    
    # KPIs Executivos
    'get_kpis_financeiros',
    'get_kpis_operacionais_executivo',
    'get_comparacao_periodo',
    'get_todos_kpis_executivos',
    
    # Gráficos
    'get_grafico_receita_diaria',
    'get_grafico_viagens_horario',
    'get_grafico_viagens_planta',
    'get_grafico_ranking_motoristas',
    'get_todos_graficos',
]
