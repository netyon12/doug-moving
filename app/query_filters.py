# Em app/query_filters.py

from .models import Bloco, Bairro, Empresa, Gerente, Supervisor, Colaborador, Motorista
from sqlalchemy import or_

def filter_blocos_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(
            or_(
                Bloco.codigo_bloco.ilike(termo_busca_like),
                Bloco.nome_bloco.ilike(termo_busca_like)
            )
        )
    return base_query

def filter_bairros_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(Bairro.nome.ilike(termo_busca_like))
    return base_query

def filter_gerentes_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(
            or_(
                Gerente.nome.ilike(termo_busca_like),
                Gerente.email.ilike(termo_busca_like)
            )
        )
    return base_query

def filter_supervisores_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(
            or_(
                Supervisor.nome.ilike(termo_busca_like),
                Supervisor.matricula.ilike(termo_busca_like),
                Supervisor.email.ilike(termo_busca_like)
            )
        )
    return base_query

def filter_colaboradores_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(
            or_(
                Colaborador.nome.ilike(termo_busca_like),
                Colaborador.matricula.ilike(termo_busca_like)
            )
        )
    return base_query

def filter_motoristas_query(base_query, filters):
    termo_busca = filters.get('busca', '')
    if termo_busca:
        termo_busca_like = f"%{termo_busca}%"
        base_query = base_query.filter(
            or_(
                Motorista.nome.ilike(termo_busca_like),
                Motorista.cpf_cnpj.ilike(termo_busca_like),
                Motorista.veiculo_placa.ilike(termo_busca_like)
            )
        )
    # O 'return' deve estar fora do 'if'
    return base_query
