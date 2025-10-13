# app/agrupamento_algoritmo.py
"""
Algoritmo inteligente para agrupamento de solicitações de viagem
VERSÃO FINAL - Compatível com o models.py ATUAL do sistema
"""
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple
from .models import Solicitacao, Viagem
from . import db


class AgrupadorViagens:
    """Classe responsável por agrupar solicitações de viagem de forma otimizada"""
    
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
        # Para corridas de Entrada, usa horario_entrada
        # Para corridas de Saída e Desligamento, usa horario_saida ou horario_desligamento
        # Normaliza para lowercase e remove acentos
        tipo_normalizado = solicitacao.tipo_corrida.lower().strip()
        tipo_normalizado = tipo_normalizado.replace('ã', 'a').replace('á', 'a').replace('í', 'i')
        
        if tipo_normalizado == 'entrada':
            return solicitacao.horario_entrada
        elif tipo_normalizado == 'saida':
            return solicitacao.horario_saida
        elif tipo_normalizado == 'desligamento':
            # Desligamento pode usar horario_desligamento OU horario_saida
            return solicitacao.horario_desligamento if solicitacao.horario_desligamento else solicitacao.horario_saida
        else:
            # Fallback: retorna qualquer horário disponível
            return solicitacao.horario_entrada or solicitacao.horario_saida or solicitacao.horario_desligamento
    
    def agrupar_solicitacoes(self, solicitacoes: List[Solicitacao]) -> List[List[Solicitacao]]:
        """
        Agrupa solicitações de forma otimizada
        
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
            bloco_id = solicitacao.colaborador.bloco_id or 0
            tipo = solicitacao.tipo_corrida
            chave = f"{bloco_id}_{tipo}"
            grupos[chave].append(solicitacao)
        
        return grupos
    
    def _agrupar_por_horario(self, solicitacoes: List[Solicitacao]) -> List[List[Solicitacao]]:
        """
        Agrupa solicitações por bloco e proximidade de horário
        
        Estratégia:
        1. Agrupa primeiro por bloco (solicitações do mesmo bloco ficam juntas)
        2. Dentro de cada bloco, agrupa por proximidade de horário
        3. Respeita janela de tempo e limite de passageiros
        """
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
    
    def criar_viagens_dos_grupos(self, grupos: List[List[Solicitacao]], created_by_user_id=None) -> Tuple[int, int]:
        """
        Cria viagens no banco de dados para cada grupo.
        
        USA APENAS OS CAMPOS QUE EXISTEM NO MODELS.PY ATUAL!
        
        REGRA IMPORTANTE: O valor da viagem é o MAIOR valor entre as solicitações, não a soma.
        
        Args:
            grupos: Lista de grupos de solicitações
            created_by_user_id: ID do usuário que está criando as viagens
            
        Returns:
            Tupla (viagens_criadas, solicitacoes_agrupadas)
        """
        import json
        
        viagens_criadas = 0
        solicitacoes_agrupadas = 0
        
        for grupo in grupos:
            if not grupo:
                continue
            
            # Pega dados da primeira solicitação (todas do grupo têm os mesmos dados base)
            primeira = grupo[0]
            
            # Coleta IDs dos colaboradores em formato JSON
            colaboradores_ids = [sol.colaborador_id for sol in grupo]
            colaboradores_json = json.dumps(colaboradores_ids)
            
            # Coleta blocos únicos do grupo
            blocos_unicos = list(set([sol.bloco_id for sol in grupo if sol.bloco_id]))
            bloco_principal = blocos_unicos[0] if blocos_unicos else None
            blocos_ids_str = ','.join(map(str, blocos_unicos)) if blocos_unicos else None
            
            # REGRA: Pega o MAIOR valor entre as solicitações (não soma)
            valores = [sol.valor for sol in grupo if sol.valor is not None]
            repasses = [sol.valor_repasse for sol in grupo if sol.valor_repasse is not None]
            
            valor_viagem = max(valores) if valores else None
            repasse_viagem = max(repasses) if repasses else None
            
            # Determina horários baseado no tipo de corrida (com normalização)
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
                # Desligamento pode usar horario_desligamento OU horario_saida
                horario_desligamento = primeira.horario_desligamento if primeira.horario_desligamento else primeira.horario_saida
            else:
                # Fallback: usa qualquer horário disponível
                horario_entrada = primeira.horario_entrada
                horario_saida = primeira.horario_saida
                horario_desligamento = primeira.horario_desligamento
            
            # Cria a viagem usando APENAS os campos que existem no models.py ATUAL
            nova_viagem = Viagem(
                # Status
                status='Pendente',
                
                # Localização
                empresa_id=primeira.empresa_id,
                planta_id=primeira.planta_id,
                bloco_id=bloco_principal,
                blocos_ids=blocos_ids_str,
                
                # Tipo de viagem
                tipo_linha=primeira.tipo_linha if hasattr(primeira, 'tipo_linha') else 'FIXA',
                tipo_corrida=tipo_normalizado,  # CORRIGIDO: usa o tipo normalizado
                
                # Horários
                horario_entrada=horario_entrada,
                horario_saida=horario_saida,
                horario_desligamento=horario_desligamento,
                
                # Passageiros
                quantidade_passageiros=len(grupo),
                colaboradores_ids=colaboradores_json,
                
                # Motorista (ainda não atribuído)
                motorista_id=None,
                nome_motorista=None,
                placa_veiculo=None,
                
                # Valores (MAIOR valor, não soma)
                valor=valor_viagem,
                valor_repasse=repasse_viagem,
                
                # Datas
                data_criacao=datetime.utcnow(),
                data_atualizacao=datetime.utcnow(),
                data_inicio=None,
                data_finalizacao=None,
                data_cancelamento=None,
                
                # Cancelamento
                motivo_cancelamento=None,
                cancelado_por_user_id=None,
                
                # Auditoria
                created_by_user_id=created_by_user_id
            )
            
            db.session.add(nova_viagem)
            db.session.flush()  # Para obter o ID
            
            # Associa as solicitações à viagem
            for solicitacao in grupo:
                solicitacao.viagem_id = nova_viagem.id
                solicitacao.status = 'Agrupada'
                solicitacoes_agrupadas += 1
            
            viagens_criadas += 1
        
        return viagens_criadas, solicitacoes_agrupadas
    
    def calcular_estatisticas(self, grupos: List[List[Solicitacao]]) -> Dict:
        """
        Calcula estatísticas sobre os grupos formados
        
        Returns:
            Dicionário com estatísticas
        """
        if not grupos:
            return {
                'total_grupos': 0,
                'total_solicitacoes': 0,
                'media_passageiros': 0,
                'taxa_ocupacao': 0,
                'grupos_completos': 0
            }
        
        total_grupos = len(grupos)
        total_solicitacoes = sum(len(g) for g in grupos)
        media_passageiros = total_solicitacoes / total_grupos if total_grupos > 0 else 0
        grupos_completos = sum(1 for g in grupos if len(g) == self.max_passageiros)
        taxa_ocupacao = (media_passageiros / self.max_passageiros * 100) if self.max_passageiros > 0 else 0
        
        return {
            'total_grupos': total_grupos,
            'total_solicitacoes': total_solicitacoes,
            'media_passageiros': round(media_passageiros, 2),
            'taxa_ocupacao': round(taxa_ocupacao, 2),
            'grupos_completos': grupos_completos
        }


def agrupar_automaticamente(solicitacoes: List[Solicitacao], 
                           max_passageiros: int = 3, 
                           janela_tempo_minutos: int = 30,
                           created_by_user_id=None) -> Dict:
    """
    Função auxiliar para agrupar solicitações automaticamente
    
    Args:
        solicitacoes: Lista de solicitações a serem agrupadas
        max_passageiros: Número máximo de passageiros por viagem
        janela_tempo_minutos: Janela de tempo em minutos
        created_by_user_id: ID do usuário que está criando as viagens
        
    Returns:
        Dicionário com resultados do agrupamento
    """
    agrupador = AgrupadorViagens(max_passageiros, janela_tempo_minutos)
    
    # Agrupa as solicitações
    grupos = agrupador.agrupar_solicitacoes(solicitacoes)
    
    # Calcula estatísticas
    estatisticas = agrupador.calcular_estatisticas(grupos)
    
    # Cria as viagens
    viagens_criadas, solicitacoes_agrupadas = agrupador.criar_viagens_dos_grupos(
        grupos, 
        created_by_user_id=created_by_user_id
    )
    
    return {
        'sucesso': True,
        'viagens_criadas': viagens_criadas,
        'solicitacoes_agrupadas': solicitacoes_agrupadas,
        'estatisticas': estatisticas
    }

