"""
Módulo de utilidades para gerenciamento de Grupos de Blocos.

Este módulo contém funções para:
- Extrair grupo de bloco a partir do código
- Agrupar solicitações por grupo de bloco
- Identificar se um conjunto de solicitações deve virar fretado ou veículo
"""

from typing import List, Dict, Tuple
from collections import defaultdict
from app.models import Solicitacao, Bloco, Configuracao


def extrair_grupo_bloco(codigo_bloco: str) -> str:
    """
    Extrai o grupo de bloco a partir do código do bloco.
    
    Exemplos:
        CPV1.1 → CPV1
        CPV1.2 → CPV1
        SJC1.3 → SJC1
        ABC → ABC (sem ponto, retorna o próprio código)
    
    Args:
        codigo_bloco: String com o código do bloco
        
    Returns:
        str: Grupo do bloco (raiz antes do último ponto)
    """
    if not codigo_bloco:
        return None
    
    # Se tem ponto, pega tudo antes do último ponto
    if '.' in codigo_bloco:
        return codigo_bloco.rsplit('.', 1)[0]
    
    # Se não tem ponto, retorna o próprio código
    return codigo_bloco


def obter_limite_fretado() -> int:
    """
    Obtém o limite configurado para considerar um grupo como fretado.
    
    Returns:
        int: Limite de passageiros (padrão: 9)
    """
    config = Configuracao.query.filter_by(chave='limite_fretado').first()
    if config and config.valor:
        try:
            return int(config.valor)
        except ValueError:
            return 9  # Valor padrão se houver erro na conversão
    return 9  # Valor padrão


def agrupar_solicitacoes_por_grupo_bloco(solicitacoes: List[Solicitacao]) -> Dict[str, List[Solicitacao]]:
    """
    Agrupa solicitações por grupo de bloco.
    
    Args:
        solicitacoes: Lista de objetos Solicitacao
        
    Returns:
        Dict: Dicionário onde a chave é o grupo de bloco e o valor é a lista de solicitações
        
    Exemplo:
        {
            'CPV1': [sol1, sol2, sol3, ...],
            'SJC1': [sol10, sol11, ...],
            'ABC': [sol20]
        }
    """
    grupos = defaultdict(list)
    
    for sol in solicitacoes:
        # ✅ CORREÇÃO: Busca bloco através do colaborador
        codigo_bloco = None
        
        # Tenta obter bloco de várias formas (compatibilidade)
        if sol.bloco and hasattr(sol.bloco, 'codigo_bloco'):
            codigo_bloco = sol.bloco.codigo_bloco
        elif sol.colaborador and sol.colaborador.bloco and hasattr(sol.colaborador.bloco, 'codigo_bloco'):
            codigo_bloco = sol.colaborador.bloco.codigo_bloco
        
        if codigo_bloco:
            grupo = extrair_grupo_bloco(codigo_bloco)
            if grupo:
                grupos[grupo].append(sol)
    
    return dict(grupos)


def classificar_grupo(solicitacoes: List[Solicitacao]) -> Tuple[str, int]:
    """
    Classifica um grupo de solicitações como 'FRETADO' ou 'VEICULO'.
    
    Args:
        solicitacoes: Lista de solicitações do mesmo grupo de bloco
        
    Returns:
        Tuple[str, int]: (tipo, quantidade)
            - tipo: 'FRETADO' se >= limite, 'VEICULO' se < limite
            - quantidade: número de solicitações
    """
    limite = obter_limite_fretado()
    quantidade = len(solicitacoes)
    
    if quantidade >= limite + 1:  # >= 10 (se limite = 9)
        return ('FRETADO', quantidade)
    else:
        return ('VEICULO', quantidade)


def separar_fretados_e_veiculos(solicitacoes: List[Solicitacao]) -> Dict[str, Dict]:
    """
    Separa solicitações em fretados e veículos baseado no grupo de bloco e quantidade.
    
    Args:
        solicitacoes: Lista de todas as solicitações a serem agrupadas
        
    Returns:
        Dict com duas chaves:
            - 'fretados': Dict[grupo_bloco, List[Solicitacao]]
            - 'veiculos': Dict[grupo_bloco, List[Solicitacao]]
            
    Exemplo:
        {
            'fretados': {
                'CPV1': [sol1, sol2, ..., sol12],  # 12 pessoas
                'SJC1': [sol20, sol21, ..., sol30]  # 11 pessoas
            },
            'veiculos': {
                'ABC': [sol40, sol41, sol42],  # 3 pessoas
                'XYZ': [sol50, sol51]  # 2 pessoas
            }
        }
    """
    # Agrupar por grupo de bloco
    grupos = agrupar_solicitacoes_por_grupo_bloco(solicitacoes)
    
    fretados = {}
    veiculos = {}
    
    # Classificar cada grupo
    for grupo_bloco, sols in grupos.items():
        tipo, quantidade = classificar_grupo(sols)
        
        if tipo == 'FRETADO':
            fretados[grupo_bloco] = sols
        else:
            veiculos[grupo_bloco] = sols
    
    return {
        'fretados': fretados,
        'veiculos': veiculos
    }


def gerar_sugestoes_fretados(solicitacoes_fretado: List[Solicitacao], grupo_bloco: str) -> List[Dict]:
    """
    Gera sugestões de divisão de fretados.
    
    Se houver muitas pessoas em um grupo, pode sugerir múltiplos fretados.
    Exemplo: 25 pessoas → Fretado 1 (25 pessoas) ou dividir em 2 fretados
    
    Args:
        solicitacoes_fretado: Lista de solicitações do grupo
        grupo_bloco: Nome do grupo de bloco
        
    Returns:
        List[Dict]: Lista de sugestões de fretados
        
    Exemplo:
        [
            {
                'nome': 'Fretado 1 - CPV1',
                'grupo_bloco': 'CPV1',
                'solicitacoes': [sol1, sol2, ..., sol25],
                'quantidade': 25,
                'blocos': ['CPV1.1', 'CPV1.2', 'CPV1.3']
            }
        ]
    """
    if not solicitacoes_fretado:
        return []
    
    # Por enquanto, uma sugestão simples: um fretado por grupo
    # Futuramente pode-se implementar lógica para dividir grupos muito grandes
    
    # Coletar todos os blocos únicos
    blocos_unicos = set()
    for sol in solicitacoes_fretado:
        if sol.bloco and sol.bloco.codigo_bloco:
            blocos_unicos.add(sol.bloco.codigo_bloco)
    
    sugestao = {
        'nome': f'Fretado - {grupo_bloco}',
        'grupo_bloco': grupo_bloco,
        'solicitacoes': solicitacoes_fretado,
        'solicitacoes_ids': [sol.id for sol in solicitacoes_fretado],
        'quantidade': len(solicitacoes_fretado),
        'blocos': sorted(list(blocos_unicos)),
        'tipo_linha': solicitacoes_fretado[0].tipo_linha if solicitacoes_fretado else None,
        'tipo_corrida': solicitacoes_fretado[0].tipo_corrida if solicitacoes_fretado else None,
    }
    
    return [sugestao]


def gerar_resumo_agrupamento(solicitacoes: List[Solicitacao]) -> Dict:
    """
    Gera um resumo completo do agrupamento com estatísticas.
    
    Args:
        solicitacoes: Lista de todas as solicitações
        
    Returns:
        Dict com estatísticas do agrupamento
        
    Exemplo:
        {
            'total_solicitacoes': 50,
            'total_fretados': 2,
            'total_veiculos': 5,
            'passageiros_fretados': 23,
            'passageiros_veiculos': 27,
            'grupos_bloco': ['CPV1', 'CPV2', 'SJC1', ...]
        }
    """
    separacao = separar_fretados_e_veiculos(solicitacoes)
    
    fretados = separacao['fretados']
    veiculos = separacao['veiculos']
    
    passageiros_fretados = sum(len(sols) for sols in fretados.values())
    passageiros_veiculos = sum(len(sols) for sols in veiculos.values())
    
    return {
        'total_solicitacoes': len(solicitacoes),
        'total_fretados': len(fretados),
        'total_veiculos': len(veiculos),
        'passageiros_fretados': passageiros_fretados,
        'passageiros_veiculos': passageiros_veiculos,
        'grupos_bloco_fretados': list(fretados.keys()),
        'grupos_bloco_veiculos': list(veiculos.keys()),
        'limite_configurado': obter_limite_fretado()
    }