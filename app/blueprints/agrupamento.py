"""
Módulo de Agrupamento
=====================

Agrupamento de solicitações.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func, or_
from io import StringIO
import io
import csv

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp


@admin_bp.route('/agrupamento')
@login_required
@permission_required(['admin', 'supervisor'])
def agrupamento():
    """Interface para visualizar e agrupar solicitações de viagem"""
    from datetime import date
    
    # Data padrão: hoje
    data_hoje = date.today().strftime('%Y-%m-%d')
    data_filtro = request.args.get('data_filtro', data_hoje)
    tipo_corrida = request.args.get('tipo_corrida', '')
    bloco_id = request.args.get('bloco_id', '')
    status_filtro = request.args.get('status', 'Pendente')
    
    # Query base
    query = Solicitacao.query.join(Colaborador).join(Supervisor)
    
    # Filtro por data (considera todos os tipos de horário)
    if data_filtro:
        data_obj = datetime.strptime(data_filtro, '%Y-%m-%d').date()
        
        # Filtra por qualquer horário (entrada, saída ou desligamento)
        # Usa func.date() para comparar apenas a data, ignorando hora e fuso
        query = query.filter(
            db.or_(
                db.and_(
                    Solicitacao.horario_entrada.isnot(None),
                    db.func.date(Solicitacao.horario_entrada) == data_obj
                ),
                db.and_(
                    Solicitacao.horario_saida.isnot(None),
                    db.func.date(Solicitacao.horario_saida) == data_obj
                ),
                db.and_(
                    Solicitacao.horario_desligamento.isnot(None),
                    db.func.date(Solicitacao.horario_desligamento) == data_obj
                )
            )
        )
    
    # Filtro por tipo de corrida
    if tipo_corrida:
        query = query.filter(Solicitacao.tipo_corrida == tipo_corrida)
    
    # Filtro por bloco
    if bloco_id:
        query = query.filter(Colaborador.bloco_id == int(bloco_id))
    
    # Filtro por status
    if status_filtro and status_filtro != 'Todos':
        query = query.filter(Solicitacao.status == status_filtro)
    
    # Filtro por permissão do usuário
    if current_user.role == 'supervisor':
        query = query.filter(Solicitacao.supervisor_id == current_user.supervisor.id)
    
    # Executa a query (ordena por qualquer horário disponível)
    solicitacoes = query.order_by(
        db.func.coalesce(
            Solicitacao.horario_entrada,
            Solicitacao.horario_saida,
            Solicitacao.horario_desligamento
        )
    ).all()
    
    # Calcula estatísticas
    total_solicitacoes = len(solicitacoes)
    blocos_distintos = len(set([s.colaborador.bloco_id for s in solicitacoes if s.colaborador.bloco_id]))
    passageiros_por_viagem = 3  # Configurável
    viagens_estimadas = (total_solicitacoes + passageiros_por_viagem - 1) // passageiros_por_viagem if total_solicitacoes > 0 else 0
    
    # Busca todos os blocos para o filtro
    todos_blocos = Bloco.query.filter_by(status='Ativo').order_by(Bloco.codigo_bloco).all()
    
    return render_template(
        'agrupamento.html',
        solicitacoes=solicitacoes,
        total_solicitacoes=total_solicitacoes,
        total_blocos_distintos=blocos_distintos,
        viagens_estimadas=viagens_estimadas,
        passageiros_por_viagem=passageiros_por_viagem,
        todos_blocos=todos_blocos,
        filtros=request.args,
        data_hoje=data_hoje
    )


@admin_bp.route('/criar_grupo_manual', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def criar_grupo_manual():
    """Cria um grupo de viagem manualmente com as solicitações selecionadas"""
    try:
        data = request.get_json()
        solicitacoes_ids = data.get('solicitacoes_ids', [])
        
        if not solicitacoes_ids:
            return jsonify({'success': False, 'message': 'Nenhuma solicitação selecionada'}), 400
        
        if len(solicitacoes_ids) > 4:
            return jsonify({'success': False, 'message': 'Máximo de 4 solicitações por grupo'}), 400
        
        # Busca as solicitações
        solicitacoes = Solicitacao.query.filter(Solicitacao.id.in_(solicitacoes_ids)).all()
        
        if len(solicitacoes) != len(solicitacoes_ids):
            return jsonify({'success': False, 'message': 'Algumas solicitações não foram encontradas'}), 404
        
        # Verifica se todas são do mesmo bloco (regra de negócio)
        blocos = set([s.colaborador.bloco_id for s in solicitacoes if s.colaborador.bloco_id])
        if len(blocos) > 1:
            return jsonify({'success': False, 'message': 'Todas as solicitações devem ser do mesmo bloco'}), 400
        
        # Cria a viagem
        nova_viagem = Viagem(
            status='Pendente',  # Aguardando atribuição de motorista
            data_inicio=datetime.utcnow()
        )
        db.session.add(nova_viagem)
        db.session.flush()  # Para obter o ID da viagem
        
        # Associa as solicitações à viagem
        for solicitacao in solicitacoes:
            solicitacao.viagem_id = nova_viagem.id
            solicitacao.status = 'Agendada'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Grupo criado com sucesso! ID da viagem: {nova_viagem.id}',
            'viagem_id': nova_viagem.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/agrupar_automatico')
@login_required
@permission_required(['admin'])
def agrupar_automatico():
    """Agrupa automaticamente as solicitações pendentes usando algoritmo inteligente"""
    try:
        from app.agrupamento_algoritmo import agrupar_automaticamente
        
        data_filtro = request.args.get('data_filtro')
        
        if not data_filtro:
            flash('Data não especificada', 'danger')
            return redirect(url_for('admin.agrupamento'))
        
        # Busca solicitações pendentes da data
        data_inicio = datetime.strptime(data_filtro, '%Y-%m-%d')
        data_fim = data_inicio.replace(hour=23, minute=59, second=59)
        
        # Query CORRIGIDA que considera entrada, saida e desligamento
        # Remove acentos e usa lowercase para comparação
        from sqlalchemy import case
        query = Solicitacao.query.filter(
            Solicitacao.status == 'Pendente',
            or_(
                # Solicitações de ENTRADA (usa horario_entrada)
                (Solicitacao.tipo_corrida == 'entrada') & 
                (Solicitacao.horario_entrada >= data_inicio) & 
                (Solicitacao.horario_entrada <= data_fim),
                
                # Solicitações de SAÍDA (usa horario_saida) - SEM acento
                (Solicitacao.tipo_corrida == 'saida') & 
                (Solicitacao.horario_saida >= data_inicio) & 
                (Solicitacao.horario_saida <= data_fim),
                
                # Solicitações de DESLIGAMENTO (usa horario_desligamento OU horario_saida)
                (Solicitacao.tipo_corrida == 'desligamento') & 
                (
                    (
                        (Solicitacao.horario_desligamento.isnot(None)) &
                        (Solicitacao.horario_desligamento >= data_inicio) & 
                        (Solicitacao.horario_desligamento <= data_fim)
                    ) |
                    (
                        (Solicitacao.horario_desligamento.is_(None)) &
                        (Solicitacao.horario_saida >= data_inicio) & 
                        (Solicitacao.horario_saida <= data_fim)
                    )
                )
            )
        )
        
        # Ordena usando uma expressão CASE para pegar o horário correto
        horario_ordenacao = case(
            (Solicitacao.tipo_corrida == 'entrada', Solicitacao.horario_entrada),
            (Solicitacao.tipo_corrida == 'saida', Solicitacao.horario_saida),
            (Solicitacao.tipo_corrida == 'desligamento', 
             db.func.coalesce(Solicitacao.horario_desligamento, Solicitacao.horario_saida)),
            else_=db.func.coalesce(Solicitacao.horario_entrada, Solicitacao.horario_saida, Solicitacao.horario_desligamento)
        )
        solicitacoes_pendentes = query.order_by(horario_ordenacao).all()
        
        if not solicitacoes_pendentes:
            flash('Nenhuma solicitação pendente encontrada para esta data', 'info')
            return redirect(url_for('admin.agrupamento'))
        
        # Busca configurações (se existirem)
        config_max_pass = Configuracao.query.filter_by(chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        config_janela = Configuracao.query.filter_by(chave='JANELA_TEMPO_AGRUPAMENTO_MIN').first()
        
        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        janela_tempo = int(config_janela.valor) if config_janela else 30
        
        # Executa o agrupamento usando o algoritmo inteligente
        resultado = agrupar_automaticamente(
            solicitacoes_pendentes, 
            max_passageiros=max_passageiros,
            janela_tempo_minutos=janela_tempo
        )
        
        db.session.commit()
        
        # Monta mensagem detalhada
        estatisticas = resultado['estatisticas']
        mensagem = (
            f"✅ Agrupamento concluído com sucesso!\n\n"
            f"📊 Estatísticas:\n"
            f"• {resultado['viagens_criadas']} viagem(ns) criada(s)\n"
            f"• {resultado['solicitacoes_agrupadas']} solicitação(ões) agrupada(s)\n"
            f"• Média de {estatisticas['media_passageiros']} passageiros por viagem\n"
            f"• Taxa de ocupação: {estatisticas['taxa_ocupacao']}%\n"
            f"• Grupos completos: {estatisticas['grupos_completos']}"
        )
        
        flash(mensagem, 'success')
        return redirect(url_for('admin.agrupamento', data_filtro=data_filtro))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao agrupar automaticamente: {str(e)}', 'danger')
        return redirect(url_for('admin.agrupamento'))


# =============================================================================
# ROTAS ADICIONAIS PARA AGRUPAMENTO COM SUGESTÕES
# =============================================================================

@admin_bp.route('/gerar_sugestoes_agrupamento')
@login_required
@permission_required(['admin', 'supervisor'])
def gerar_sugestoes_agrupamento():
    """Gera sugestões de agrupamento sem salvar no banco"""
    try:
        from app.agrupamento_algoritmo import AgrupadorViagens
        from datetime import date
        import json
        
        data_filtro = request.args.get('data_filtro')
        if not data_filtro:
            data_filtro = date.today().strftime('%Y-%m-%d')
        
        # Busca solicitações pendentes da data
        data_inicio = datetime.strptime(data_filtro, '%Y-%m-%d')
        data_fim = data_inicio.replace(hour=23, minute=59, second=59)
        
        # Query CORRIGIDA que considera entrada, saida e desligamento
        from sqlalchemy import case
        query = Solicitacao.query.filter(
            Solicitacao.status == 'Pendente',
            or_(
                # Solicitações de ENTRADA (usa horario_entrada)
                (Solicitacao.tipo_corrida == 'entrada') & 
                (Solicitacao.horario_entrada >= data_inicio) & 
                (Solicitacao.horario_entrada <= data_fim),
                
                # Solicitações de SAÍDA (usa horario_saida) - SEM acento
                (Solicitacao.tipo_corrida == 'saida') & 
                (Solicitacao.horario_saida >= data_inicio) & 
                (Solicitacao.horario_saida <= data_fim),
                
                # Solicitações de DESLIGAMENTO (usa horario_desligamento OU horario_saida)
                (Solicitacao.tipo_corrida == 'desligamento') & 
                (
                    (
                        (Solicitacao.horario_desligamento.isnot(None)) &
                        (Solicitacao.horario_desligamento >= data_inicio) & 
                        (Solicitacao.horario_desligamento <= data_fim)
                    ) |
                    (
                        (Solicitacao.horario_desligamento.is_(None)) &
                        (Solicitacao.horario_saida >= data_inicio) & 
                        (Solicitacao.horario_saida <= data_fim)
                    )
                )
            )
        )
        
        # Filtro por permissão do usuário
        if current_user.role == 'supervisor':
            query = query.filter(Solicitacao.supervisor_id == current_user.supervisor.id)
        
        # Ordena usando uma expressão CASE para pegar o horário correto
        horario_ordenacao = case(
            (Solicitacao.tipo_corrida == 'entrada', Solicitacao.horario_entrada),
            (Solicitacao.tipo_corrida == 'saida', Solicitacao.horario_saida),
            (Solicitacao.tipo_corrida == 'desligamento', 
             db.func.coalesce(Solicitacao.horario_desligamento, Solicitacao.horario_saida)),
            else_=db.func.coalesce(Solicitacao.horario_entrada, Solicitacao.horario_saida, Solicitacao.horario_desligamento)
        )
        solicitacoes_pendentes = query.order_by(horario_ordenacao).all()
        
        if not solicitacoes_pendentes:
            flash('Nenhuma solicitação pendente encontrada para esta data', 'info')
            return redirect(url_for('admin.agrupamento'))
        
        # Busca configurações
        config_max_pass = Configuracao.query.filter_by(chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        config_janela = Configuracao.query.filter_by(chave='JANELA_TEMPO_AGRUPAMENTO_MIN').first()
        
        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        janela_tempo = int(config_janela.valor) if config_janela else 30
        
        # Cria o agrupador e gera os grupos
        agrupador = AgrupadorViagens(max_passageiros, janela_tempo)
        grupos = agrupador.agrupar_solicitacoes(solicitacoes_pendentes)
        estatisticas = agrupador.calcular_estatisticas(grupos)
        
        # Converte grupos para JSON (com dados completos)
        grupos_json = []
        for grupo in grupos:
            grupo_data = []
            for s in grupo:
                # Determina o horário correto baseado no tipo de corrida
                tipo_lower = s.tipo_corrida.lower() if s.tipo_corrida else ''
                if tipo_lower == 'entrada':
                    horario = s.horario_entrada.strftime('%H:%M') if s.horario_entrada else 'N/A'
                else:
                    horario = s.horario_saida.strftime('%H:%M') if s.horario_saida else 'N/A'
                
                grupo_data.append({
                    'id': s.id,
                    'colaborador_nome': s.colaborador.nome if s.colaborador else 'N/A',
                    'bloco_codigo': s.colaborador.bloco.codigo_bloco if s.colaborador and s.colaborador.bloco else 'N/A',
                    'tipo_corrida': s.tipo_corrida,
                    'horario': horario
                })
            grupos_json.append(grupo_data)
        
        # Armazena na sessão para uso posterior
        from flask import session
        session['grupos_sugeridos'] = grupos_json
        session['data_agrupamento'] = data_filtro
        
        return render_template(
            'agrupamento_sugestoes.html',
            grupos=grupos,
            grupos_json=json.dumps(grupos_json),
            estatisticas=estatisticas,
            data_filtro=data_filtro
        )
        
    except Exception as e:
        flash(f'Erro ao gerar sugestões: {str(e)}', 'danger')
        return redirect(url_for('admin.agrupamento'))


@admin_bp.route('/finalizar_agrupamento', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def finalizar_agrupamento():
    """Finaliza o agrupamento criando viagens no banco de dados"""
    try:
        data = request.get_json()
        grupos = data.get('grupos', [])
        
        if not grupos:
            return jsonify({'success': False, 'message': 'Nenhum grupo para finalizar'}), 400
        
        viagens_criadas = 0
        solicitacoes_agrupadas = 0
        
        for grupo_ids in grupos:
            if not grupo_ids:
                continue
            
            # Busca as solicitações do grupo
            solicitacoes = Solicitacao.query.filter(Solicitacao.id.in_(grupo_ids)).all()
            
            if not solicitacoes:
                continue
            
            # Pega dados da primeira solicitação (todas do grupo têm os mesmos dados base)
            primeira = solicitacoes[0]
            
            # Coleta IDs dos colaboradores em formato JSON
            import json
            colaboradores_ids = [sol.colaborador_id for sol in solicitacoes]
            colaboradores_json = json.dumps(colaboradores_ids)
            
            # Coleta blocos únicos do grupo
            blocos_unicos = list(set([sol.bloco_id for sol in solicitacoes if sol.bloco_id]))
            bloco_principal = blocos_unicos[0] if blocos_unicos else None
            blocos_ids_str = ','.join(map(str, blocos_unicos)) if blocos_unicos else None
            
            # REGRA: Pega o MAIOR valor entre as solicitações (não soma)
            valores = [sol.valor for sol in solicitacoes if sol.valor is not None]
            repasses = [sol.valor_repasse for sol in solicitacoes if sol.valor_repasse is not None]
            
            valor_viagem = max(valores) if valores else None
            repasse_viagem = max(repasses) if repasses else None
            
            # Determina horários e tipo baseado no tipo de corrida (com normalização)
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
                # Fallback: usa qualquer horário disponível
                horario_entrada = primeira.horario_entrada
                horario_saida = primeira.horario_saida
                horario_desligamento = primeira.horario_desligamento
            
            # Cria a viagem COM TODOS OS DADOS (corrigido)
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
                tipo_corrida=tipo_normalizado,  # Usa o tipo normalizado
                
                # Horários
                horario_entrada=horario_entrada,
                horario_saida=horario_saida,
                horario_desligamento=horario_desligamento,
                
                # Passageiros
                quantidade_passageiros=len(solicitacoes),
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
                created_by_user_id=current_user.id
            )
            db.session.add(nova_viagem)
            db.session.flush()  # Para obter o ID da viagem
            
            # Associa as solicitações à viagem
            for solicitacao in solicitacoes:
                solicitacao.viagem_id = nova_viagem.id
                solicitacao.status = 'Agrupada'  # Corrigido: era 'Agendada', agora é 'Agrupada'
                solicitacoes_agrupadas += 1
            
            viagens_criadas += 1
        
        db.session.commit()
        
        # Limpa a sessão
        from flask import session
        session.pop('grupos_sugeridos', None)
        session.pop('data_agrupamento', None)
        
        return jsonify({
            'success': True,
            'message': f'✅ Agrupamento finalizado com sucesso! {viagens_criadas} viagem(ns) criada(s) com {solicitacoes_agrupadas} solicitação(ões) agrupada(s).',
            'viagens_criadas': viagens_criadas,
            'solicitacoes_agrupadas': solicitacoes_agrupadas
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/desfazer_grupo', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def desfazer_grupo():
    """Remove um grupo específico das sugestões"""
    try:
        data = request.get_json()
        grupo_index = data.get('grupo_index')
        grupos = data.get('grupos', [])
        
        if grupo_index is None or grupo_index < 0 or grupo_index >= len(grupos):
            return jsonify({'success': False, 'message': 'Índice de grupo inválido'}), 400
        
        # Remove o grupo
        grupos.pop(grupo_index)
        
        # Atualiza na sessão
        from flask import session
        session['grupos_sugeridos'] = grupos
        
        return jsonify({'success': True, 'grupos': grupos})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/remover_solicitacao_grupo', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def remover_solicitacao_grupo():
    """Remove uma solicitação específica de um grupo"""
    try:
        data = request.get_json()
        grupo_index = data.get('grupo_index')
        solicitacao_id = data.get('solicitacao_id')
        grupos = data.get('grupos', [])
        
        if grupo_index is None or grupo_index < 0 or grupo_index >= len(grupos):
            return jsonify({'success': False, 'message': 'Índice de grupo inválido'}), 400
        
        # Remove a solicitação do grupo
        if solicitacao_id in grupos[grupo_index]:
            grupos[grupo_index].remove(solicitacao_id)
        
        # Se o grupo ficou vazio, remove o grupo
        if not grupos[grupo_index]:
            grupos.pop(grupo_index)
        
        # Atualiza na sessão
        from flask import session
        session['grupos_sugeridos'] = grupos
        
        return jsonify({'success': True, 'grupos': grupos})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/adicionar_solicitacao_grupo', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def adicionar_solicitacao_grupo():
    """Adiciona uma solicitação a um grupo existente"""
    try:
        data = request.get_json()
        grupo_index = data.get('grupo_index')
        solicitacao_id = data.get('solicitacao_id')
        grupos = data.get('grupos', [])
        
        if grupo_index is None or grupo_index < 0 or grupo_index >= len(grupos):
            return jsonify({'success': False, 'message': 'Índice de grupo inválido'}), 400
        
        # Busca configuração de máximo de passageiros
        config_max_pass = Configuracao.query.filter_by(chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        
        # Verifica se o grupo não está cheio
        if len(grupos[grupo_index]) >= max_passageiros:
            return jsonify({'success': False, 'message': f'Grupo já possui o máximo de {max_passageiros} passageiros'}), 400
        
        # Verifica se a solicitação já está em algum grupo
        for grupo in grupos:
            if solicitacao_id in grupo:
                return jsonify({'success': False, 'message': 'Solicitação já está em outro grupo'}), 400
        
        # Adiciona a solicitação ao grupo
        grupos[grupo_index].append(solicitacao_id)
        
        # Atualiza na sessão
        from flask import session
        session['grupos_sugeridos'] = grupos
        
        return jsonify({'success': True, 'grupos': grupos})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/criar_novo_grupo', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def criar_novo_grupo():
    """Cria um novo grupo vazio nas sugestões"""
    try:
        data = request.get_json()
        grupos = data.get('grupos', [])
        
        # Adiciona um novo grupo vazio
        grupos.append([])
        
        # Atualiza na sessão
        from flask import session
        session['grupos_sugeridos'] = grupos
        
        return jsonify({'success': True, 'grupos': grupos})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/mesclar_grupos', methods=['POST'])
@login_required
@permission_required(['admin', 'supervisor'])
def mesclar_grupos():
    """Mescla dois grupos em um só"""
    try:
        data = request.get_json()
        grupo_index_1 = data.get('grupo_index_1')
        grupo_index_2 = data.get('grupo_index_2')
        grupos = data.get('grupos', [])
        
        if (grupo_index_1 is None or grupo_index_2 is None or 
            grupo_index_1 < 0 or grupo_index_2 < 0 or
            grupo_index_1 >= len(grupos) or grupo_index_2 >= len(grupos) or
            grupo_index_1 == grupo_index_2):
            return jsonify({'success': False, 'message': 'Índices de grupo inválidos'}), 400
        
        # Busca configuração de máximo de passageiros
        config_max_pass = Configuracao.query.filter_by(chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        
        # Verifica se a mesclagem não excede o limite
        total_passageiros = len(grupos[grupo_index_1]) + len(grupos[grupo_index_2])
        if total_passageiros > max_passageiros:
            return jsonify({'success': False, 'message': f'Mesclagem excederia o máximo de {max_passageiros} passageiros'}), 400
        
        # Mescla os grupos
        grupos[grupo_index_1].extend(grupos[grupo_index_2])
        grupos.pop(grupo_index_2)
        
        # Atualiza na sessão
        from flask import session
        session['grupos_sugeridos'] = grupos
        
        return jsonify({'success': True, 'grupos': grupos})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500




# =============================================================================
# ROTAS DE GERENCIAMENTO DE VIAGENS
# =============================================================================

