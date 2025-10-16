"""
Algoritmo inteligente para agrupamento de solicitações de viagem - VERSÃO 2.0
Inclui suporte para Fretados (grupos com 10+ passageiros do mesmo grupo de bloco)
"""
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple
from .models import Solicitacao, Viagem, Fretado
from .utils.grupo_blocos import (
    separar_fretados_e_veiculos,
    gerar_sugestoes_fretados,
    gerar_resumo_agrupamento
)
from . import db
import json


class AgrupadorViagensV2:
    """
    Classe responsável por agrupar solicitações de viagem de forma otimizada.
    Versão 2.0 com suporte a Fretados.
    """
    
    def __init__(self, max_passageiros=3, janela_tempo_minutos=30):
        """
        Inicializa o agrupador
        
        Args:
            max_passageiros: Número máximo de passageiros por viagem (padrão: 3)
            janela_tempo_minutos: Janela de tempo para considerar horários próximos (padrão: 30 min)
        """
        self.max_passageiros = max_passageiros
        self.janela_tempo = timedelta(minutes=janela_tempo_minutos)
    
    def _obter_horario_relevante(self, solicitacao: Solicitacao) -> datetime:
        """
        Obtém o horário relevante da solicitação baseado no tipo de corrida
        
        Args:
            solicitacao: Solicitação a ser analisada
            
        Returns:
            Horário relevante (entrada ou saída)
        """
        tipo_normalizado = solicitacao.tipo_corrida.lower().strip()
        tipo_normalizado = tipo_normalizado.replace('ã', 'a').replace('á', 'a').replace('í', 'i')
        
        if tipo_normalizado == 'entrada':
            return solicitacao.horario_entrada
        elif tipo_normalizado == 'saida':
            return solicitacao.horario_saida
        elif tipo_normalizado == 'desligamento':
            return solicitacao.horario_desligamento if solicitacao.horario_desligamento else solicitacao.horario_saida
        else:
            return solicitacao.horario_entrada or solicitacao.horario_saida or solicitacao.horario_desligamento
    
    def processar_agrupamento_completo(self, solicitacoes: List[Solicitacao]) -> Dict:
        """
        Processa o agrupamento completo, separando fretados e veículos.
        
        Args:
            solicitacoes: Lista de solicitações a serem agrupadas
            
        Returns:
            Dict com fretados e veículos separados:
            {
                'fretados': {
                    'CPV1': {
                        'sugestoes': [lista de sugestões de fretados],
                        'solicitacoes': [lista de solicitações]
                    }
                },
                'veiculos': {
                    'SJC1': [lista de grupos de veículos]
                },
                'resumo': {estatísticas}
            }
        """
        if not solicitacoes:
            return {
                'fretados': {},
                'veiculos': {},
                'resumo': {}
            }
        
        # Separar fretados e veículos
        separacao = separar_fretados_e_veiculos(solicitacoes)
        
        fretados_dict = separacao['fretados']
        veiculos_dict = separacao['veiculos']
        
        # Processar fretados
        fretados_processados = {}
        for grupo_bloco, solicitacoes_fretado in fretados_dict.items():
            sugestoes = gerar_sugestoes_fretados(solicitacoes_fretado, grupo_bloco)
            fretados_processados[grupo_bloco] = {
                'sugestoes': sugestoes,
                'solicitacoes': solicitacoes_fretado
            }
        
        # Processar veículos (usa lógica antiga de agrupamento)
        veiculos_processados = {}
        for grupo_bloco, solicitacoes_veiculo in veiculos_dict.items():
            grupos_veiculo = self.agrupar_solicitacoes_veiculo(solicitacoes_veiculo)
            veiculos_processados[grupo_bloco] = grupos_veiculo
        
        # Gerar resumo
        resumo = gerar_resumo_agrupamento(solicitacoes)
        
        return {
            'fretados': fretados_processados,
            'veiculos': veiculos_processados,
            'resumo': resumo
        }
    
    def agrupar_solicitacoes_veiculo(self, solicitacoes: List[Solicitacao]) -> List[List[Solicitacao]]:
        """
        Agrupa solicitações de veículo (lógica antiga, para grupos pequenos)
        
        Regras de agrupamento:
        1. Mesmo bloco (localização geográfica)
        2. Mesmo tipo de corrida (Entrada/Saída/Desligamento)
        3. Horários próximos (dentro da janela de tempo)
        4. Máximo de passageiros por viagem
        
        Args:
            solicitacoes: Lista de solicitações a serem agrupadas
            
        Returns:
            Lista de grupos (cada grupo é uma lista de solicitações)
        """
        if not solicitacoes:
            return []
        
        # Passo 1: Separar por bloco e tipo de corrida
        grupos_base = self._separar_por_bloco_e_tipo(solicitacoes)
        
        # Passo 2: Dentro de cada grupo base, agrupar por proximidade de horário
        grupos_finais = []
        for grupo_base in grupos_base.values():
            grupos_finais.extend(self._agrupar_por_horario(grupo_base))
        
        return grupos_finais
    
    def _separar_por_bloco_e_tipo(self, solicitacoes: List[Solicitacao]) -> Dict[str, List[Solicitacao]]:
        """Separa solicitações por bloco e tipo de corrida"""
        grupos = defaultdict(list)
        
        for solicitacao in solicitacoes:
            bloco_id = solicitacao.bloco_id or 0
            tipo = solicitacao.tipo_corrida
            chave = f"{bloco_id}_{tipo}"
            grupos[chave].append(solicitacao)
        
        return grupos
    
    def _agrupar_por_horario(self, solicitacoes: List[Solicitacao]) -> List[List[Solicitacao]]:
        """Agrupa solicitações por proximidade de horário"""
        if not solicitacoes:
            return []
        
        # Agrupa solicitações por bloco
        solicitacoes_por_bloco = {}
        for solicitacao in solicitacoes:
            bloco_id = solicitacao.bloco_id
            if bloco_id not in solicitacoes_por_bloco:
                solicitacoes_por_bloco[bloco_id] = []
            solicitacoes_por_bloco[bloco_id].append(solicitacao)
        
        # Processa cada bloco separadamente
        grupos = []
        for bloco_id, solicitacoes_bloco in solicitacoes_por_bloco.items():
            # Ordena solicitações do bloco por horário relevante
            solicitacoes_ordenadas = sorted(
                solicitacoes_bloco,
                key=lambda s: self._obter_horario_relevante(s)
            )
            
            # Agrupa por proximidade de horário dentro do bloco
            grupo_atual = [solicitacoes_ordenadas[0]]
            horario_referencia = self._obter_horario_relevante(solicitacoes_ordenadas[0])
            
            for solicitacao in solicitacoes_ordenadas[1:]:
                horario_atual = self._obter_horario_relevante(solicitacao)
                diferenca_tempo = abs(horario_atual - horario_referencia)
                
                # Verifica se pode adicionar ao grupo atual
                if (diferenca_tempo <= self.janela_tempo and 
                    len(grupo_atual) < self.max_passageiros):
                    # Adiciona ao grupo atual
                    grupo_atual.append(solicitacao)
                else:
                    # Fecha o grupo atual e inicia um novo
                    grupos.append(grupo_atual)
                    grupo_atual = [solicitacao]
                    horario_referencia = horario_atual
            
            # Adiciona o último grupo do bloco
            if grupo_atual:
                grupos.append(grupo_atual)
        
        return grupos
    
    def criar_fretados(self, sugestoes_fretados: List[Dict], created_by_user_id=None) -> Tuple[int, int]:
        """
        Cria registros de fretados no banco de dados.
        
        Args:
            sugestoes_fretados: Lista de sugestões de fretados
            created_by_user_id: ID do usuário que está criando os fretados
            
        Returns:
            Tupla (fretados_criados, solicitacoes_agrupadas)
        """
        fretados_criados = 0
        solicitacoes_agrupadas = 0
        
        for sugestao in sugestoes_fretados:
            solicitacoes = sugestao['solicitacoes']
            if not solicitacoes:
                continue
            
            primeira = solicitacoes[0]
            
            # Coleta IDs dos colaboradores
            colaboradores_ids = [sol.colaborador_id for sol in solicitacoes]
            colaboradores_json = json.dumps(colaboradores_ids)
            
            # Coleta blocos únicos
            blocos_unicos = list(set([sol.bloco_id for sol in solicitacoes if sol.bloco_id]))
            bloco_principal = blocos_unicos[0] if blocos_unicos else None
            blocos_ids_str = ','.join(map(str, blocos_unicos)) if blocos_unicos else None
            
            # Valores (maior valor, não soma)
            valores = [sol.valor for sol in solicitacoes if sol.valor is not None]
            repasses = [sol.valor_repasse for sol in solicitacoes if sol.valor_repasse is not None]
            
            valor_fretado = max(valores) if valores else None
            repasse_fretado = max(repasses) if repasses else None
            
            # Determina horários
            tipo_normalizado = primeira.tipo_corrida.lower().strip()
            tipo_normalizado = tipo_normalizado.replace('ã', 'a').replace('á', 'a').replace('í', 'i')
            
            if tipo_normalizado == 'entrada':
                horario_entrada = primeira.horario_entrada
                horario_saida = None
                horario_desligamento = None
            elif tipo_normalizado == 'saida':
                horario_entrada = None
                horario_saida = primeira.horario_saida
                horario_desligamento = None
            elif tipo_normalizado == 'desligamento':
                horario_entrada = None
                horario_saida = None
                horario_desligamento = primeira.horario_desligamento if primeira.horario_desligamento else primeira.horario_saida
            else:
                horario_entrada = primeira.horario_entrada
                horario_saida = primeira.horario_saida
                horario_desligamento = primeira.horario_desligamento
            
            # Cria o fretado
            novo_fretado = Fretado(
                status='Fretado',
                empresa_id=primeira.empresa_id,
                planta_id=primeira.planta_id,
                bloco_id=bloco_principal,
                blocos_ids=blocos_ids_str,
                grupo_bloco=sugestao.get('blocos', [''])[0] if sugestao.get('blocos') else None,
                tipo_linha=primeira.tipo_linha if hasattr(primeira, 'tipo_linha') else 'FIXA',
                tipo_corrida=tipo_normalizado,
                horario_entrada=horario_entrada,
                horario_saida=horario_saida,
                horario_desligamento=horario_desligamento,
                quantidade_passageiros=len(solicitacoes),
                colaboradores_ids=colaboradores_json,
                valor=valor_fretado,
                valor_repasse=repasse_fretado,
                created_by_user_id=created_by_user_id,
                data_criacao=datetime.utcnow(),
                data_atualizacao=datetime.utcnow()
            )
            
            db.session.add(novo_fretado)
            db.session.flush()
            
            # Associa as solicitações ao fretado
            for solicitacao in solicitacoes:
                solicitacao.fretado_id = novo_fretado.id
                solicitacao.status = 'Fretado'
                solicitacoes_agrupadas += 1
            
            fretados_criados += 1
        
        return fretados_criados, solicitacoes_agrupadas
    
    def criar_viagens(self, grupos_veiculos: List[List[Solicitacao]], created_by_user_id=None) -> Tuple[int, int]:
        """
        Cria viagens no banco de dados para grupos de veículos.
        (Lógica antiga, mantida para compatibilidade)
        """
        viagens_criadas = 0
        solicitacoes_agrupadas = 0
        
        for grupo in grupos_veiculos:
            if not grupo:
                continue
            
            primeira = grupo[0]
            
            colaboradores_ids = [sol.colaborador_id for sol in grupo]
            colaboradores_json = json.dumps(colaboradores_ids)
            
            blocos_unicos = list(set([sol.bloco_id for sol in grupo if sol.bloco_id]))
            bloco_principal = blocos_unicos[0] if blocos_unicos else None
            blocos_ids_str = ','.join(map(str, blocos_unicos)) if blocos_unicos else None
            
            valores = [sol.valor for sol in grupo if sol.valor is not None]
            repasses = [sol.valor_repasse for sol in grupo if sol.valor_repasse is not None]
            
            valor_viagem = max(valores) if valores else None
            repasse_viagem = max(repasses) if repasses else None
            
            tipo_normalizado = primeira.tipo_corrida.lower().strip()
            tipo_normalizado = tipo_normalizado.replace('ã', 'a').replace('á', 'a').replace('í', 'i')
            
            if tipo_normalizado == 'entrada':
                horario_entrada = primeira.horario_entrada
                horario_saida = None
                horario_desligamento = None
            elif tipo_normalizado == 'saida':
                horario_entrada = None
                horario_saida = primeira.horario_saida
                horario_desligamento = None
            elif tipo_normalizado == 'desligamento':
                horario_entrada = None
                horario_saida = None
                horario_desligamento = primeira.horario_desligamento if primeira.horario_desligamento else primeira.horario_saida
            else:
                horario_entrada = primeira.horario_entrada
                horario_saida = primeira.horario_saida
                horario_desligamento = primeira.horario_desligamento
            
            nova_viagem = Viagem(
                status='Pendente',
                empresa_id=primeira.empresa_id,
                planta_id=primeira.planta_id,
                bloco_id=bloco_principal,
                blocos_ids=blocos_ids_str,
                tipo_linha=primeira.tipo_linha if hasattr(primeira, 'tipo_linha') else 'FIXA',
                tipo_corrida=tipo_normalizado,
                horario_entrada=horario_entrada,
                horario_saida=horario_saida,
                horario_desligamento=horario_desligamento,
                quantidade_passageiros=len(grupo),
                colaboradores_ids=colaboradores_json,
                motorista_id=None,
                nome_motorista=None,
                placa_veiculo=None,
                valor=valor_viagem,
                valor_repasse=repasse_viagem,
                data_criacao=datetime.utcnow(),
                data_atualizacao=datetime.utcnow(),
                data_inicio=None,
                data_finalizacao=None,
                data_cancelamento=None,
                motivo_cancelamento=None,
                cancelado_por_user_id=None,
                created_by_user_id=created_by_user_id
            )
            
            db.session.add(nova_viagem)
            db.session.flush()
            
            for solicitacao in grupo:
                solicitacao.viagem_id = nova_viagem.id
                solicitacao.status = 'Agrupada'
                solicitacoes_agrupadas += 1
            
            viagens_criadas += 1
        
        return viagens_criadas, solicitacoes_agrupadas


def gerar_sugestoes_agrupamento(solicitacoes: List[Solicitacao], 
                                max_passageiros: int = 3, 
                                janela_tempo_minutos: int = 30) -> Dict:
    """
    Gera sugestões de agrupamento (fretados + veículos) SEM salvar no banco.
    
    Args:
        solicitacoes: Lista de solicitações
        max_passageiros: Máximo de passageiros por veículo
        janela_tempo_minutos: Janela de tempo em minutos
        
    Returns:
        Dict com sugestões de fretados e veículos
    """
    agrupador = AgrupadorViagensV2(max_passageiros, janela_tempo_minutos)
    return agrupador.processar_agrupamento_completo(solicitacoes)


def confirmar_agrupamento(sugestoes: Dict, created_by_user_id=None) -> Dict:
    """
    Confirma o agrupamento e salva fretados e viagens no banco.
    
    Args:
        sugestoes: Dict retornado por gerar_sugestoes_agrupamento()
        created_by_user_id: ID do usuário
        
    Returns:
        Dict com resultados
    """
    agrupador = AgrupadorViagensV2()
    
    fretados_criados = 0
    viagens_criadas = 0
    solicitacoes_agrupadas = 0
    
    # Criar fretados
    for grupo_bloco, dados in sugestoes['fretados'].items():
        f_criados, s_agrupadas = agrupador.criar_fretados(
            dados['sugestoes'], 
            created_by_user_id
        )
        fretados_criados += f_criados
        solicitacoes_agrupadas += s_agrupadas
    
    # Criar viagens
    for grupo_bloco, grupos in sugestoes['veiculos'].items():
        v_criadas, s_agrupadas = agrupador.criar_viagens(
            grupos, 
            created_by_user_id
        )
        viagens_criadas += v_criadas
        solicitacoes_agrupadas += s_agrupadas
    
    db.session.commit()
    
    return {
        'sucesso': True,
        'fretados_criados': fretados_criados,
        'viagens_criadas': viagens_criadas,
        'solicitacoes_agrupadas': solicitacoes_agrupadas,
        'resumo': sugestoes['resumo']
    }