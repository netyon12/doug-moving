"""
Módulo de Modelos do Sistema Go Mobi
====================================

Este módulo centraliza todos os modelos SQLAlchemy do sistema,
organizados por categoria para facilitar manutenção.

Estrutura:
- models_cad_base.py: Entidades cadastrais base (Empresa, Planta, Turno, Bloco, Bairro, CentroCusto)
- models_cad_pessoas.py: Perfis de usuários (Gerente, Supervisor, Colaborador, Motorista)
- models_processos.py: Fluxo operacional (Viagem, Solicitacao, ViagemHoraParada)
- models_config.py: Autenticação e auditoria (User, Configuracao, AuditLog, ViagemAuditoria)
- models_financeiro.py: Gestão financeira (FinContasReceber, FinContasPagar e associações)
- models_fretado.py: Módulo de fretados (Fretado)
"""

from datetime import datetime, timedelta

# Função auxiliar para horário de Brasília (UTC-3)
def horario_brasil():
    return datetime.utcnow() - timedelta(hours=3)

# Importar db do app (não criar aqui para evitar circular import)
from app import db

# Importar todos os modelos de cadastros base
from .models_cad_base import (
    Empresa, Planta, CentroCusto, Turno, Bloco, Bairro
)

# Importar todos os modelos de cadastros de pessoas
from .models_cad_pessoas import (
    Gerente, Supervisor, Colaborador, Motorista
)

# Importar todos os modelos de processos
from .models_processos import (
    Viagem, Solicitacao, ViagemHoraParada
)

# Importar todos os modelos de configuração
from .models_config import (
    User, Configuracao, AuditLog, ViagemAuditoria
)

# Importar todos os modelos financeiros
from .models_financeiro import (
    FinContasReceber, FinReceberViagens,
    FinContasPagar, FinPagarViagens
)

# Importar modelo de fretado
from .models_fretado import Fretado

# Exportar tudo para manter compatibilidade com importações existentes
__all__ = [
    # Função auxiliar
    'horario_brasil',
    
    # Cadastros Base
    'Empresa', 'Planta', 'CentroCusto', 'Turno', 'Bloco', 'Bairro',
    
    # Cadastros Pessoas
    'Gerente', 'Supervisor', 'Colaborador', 'Motorista',
    
    # Processos
    'Viagem', 'Solicitacao', 'ViagemHoraParada',
    
    # Config
    'User', 'Configuracao', 'AuditLog', 'ViagemAuditoria',
    
    # Financeiro
    'FinContasReceber', 'FinReceberViagens',
    'FinContasPagar', 'FinPagarViagens',
    
    # Fretado
    'Fretado'
]
