"""
Blueprint Admin - Módulo Principal
===================================

Este é o módulo orquestrador do admin que cria o blueprint e
importa todos os sub-módulos especializados.

Estrutura Modular:
- admin.py (este arquivo): Cria o blueprint e importa módulos
- dashboard.py: Dashboard principal com KPIs
- cadastros.py: CRUD de cadastros básicos
- colaboradores.py: CRUD de colaboradores
- solicitacoes.py: CRUD de solicitações
- agrupamento.py: Agrupamento de solicitações
- viagens.py: Gestão de viagens
- configuracoes.py: Configurações e importações

Autor: Sistema Go Mobi
Data: 2024-10-13
"""

from flask import Blueprint
import logging

# =============================================================================
# CRIAÇÃO DO BLUEPRINT
# =============================================================================

# Cria o blueprint admin que será usado por todos os módulos
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# =============================================================================
# IMPORTAÇÃO DOS MÓDULOS
# =============================================================================

# Importa todos os módulos especializados
# Cada módulo registra suas rotas usando @admin_bp.route()

from . import dashboard
from . import cadastros
from . import colaboradores
from . import solicitacoes
from . import agrupamento
from . import viagens
from . import configuracoes
from . import fretados
# =============================================================================
# INFORMAÇÕES DO MÓDULO
# =============================================================================

__version__ = '2.0.0'
__author__ = 'Sistema Go Mobi'
__description__ = 'Blueprint Admin Modularizado'

# Lista de módulos carregados
MODULOS_CARREGADOS = [
    'dashboard',
    'cadastros',
    'colaboradores',
    'solicitacoes',
    'agrupamento',
    'viagens',
    'fretados',
    'configuracoes',
]


logger = logging.getLogger(__name__)

logger.info(f"✅ Blueprint Admin carregado (v{__version__})")
logger.info(f"   Módulos ativos: {', '.join(MODULOS_CARREGADOS)}")

#print(f"✅ Blueprint Admin carregado (v{__version__})")
#print(f"   Módulos ativos: {', '.join(MODULOS_CARREGADOS)}")

