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
from sqlalchemy.orm import joinedload
from io import StringIO
import io
import csv
import logging

# Configurar logger para este módulo
logger = logging.getLogger(__name__)

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Fretado, Configuracao
)

from ..decorators import permission_required
from app.decorators import agrupamento_required
from app import query_filters

from .admin import admin_bp
from app.services.notification_service import notification_service

# IMPORTAR SISTEMA DE AUDITORIA
from ..utils.admin_audit import log_audit, log_viagem_audit, AuditAction


def formatar_horario(horario):
    """Formata horário para HH:MM, funciona com datetime ou string"""
    if not horario:
        return ''
    # Se for datetime, usa strftime
    if hasattr(horario, 'strftime'):
        return horario.strftime('%H:%M')
    # Se for string, extrai HH:MM
    horario_str = str(horario)
    if len(horario_str) >= 16:  # Formato: "2025-10-21 20:36:00"
        return horario_str[11:16]
    return horario_str


def serializar_solicitacao(sol):
    """Converte objeto Solicitacao em dicionário"""
    return {
        'id': sol.id,
        'colaborador_id': sol.colaborador_id,
        'colaborador_nome': sol.colaborador.nome if sol.colaborador else '',
        'bloco_id': sol.colaborador.bloco_id if sol.colaborador else None,
        'bloco_codigo': sol.colaborador.bloco.codigo_bloco if sol.colaborador and sol.colaborador.bloco else '',
        'tipo_corrida': sol.tipo_corrida,
        'horario_entrada': formatar_horario(sol.horario_entrada),
        'horario_saida': formatar_horario(sol.horario_saida),
        'horario_desligamento': formatar_horario(sol.horario_desligamento)
    }


@admin_bp.route('/agrupamento')
@login_required
@agrupamento_required
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

    # Filtro por planta (opcional - apenas para Gerente)
    planta_filtro = request.args.get('planta_id')
    if planta_filtro and current_user.role == 'gerente':
        # Join com Colaborador já existe na query base (linha 80)
        query = query.filter(Colaborador.planta_id == int(planta_filtro))

    # Filtro por bloco
    if bloco_id:
        query = query.filter(Colaborador.bloco_id == int(bloco_id))

    # Filtro por status
    if status_filtro and status_filtro != 'Todos':
        query = query.filter(Solicitacao.status == status_filtro)

    # Filtro por permissão do usuário
    if current_user.role == 'supervisor':
        query = query.filter(Solicitacao.supervisor_id ==
                             current_user.supervisor.id)
    elif current_user.role == 'gerente':
        # Gerente vê solicitações de todas as suas plantas
        gerente = Gerente.query.filter_by(user_id=current_user.id).first()
        if gerente:
            plantas_ids = [p.id for p in gerente.plantas.all()]
            # Join com Colaborador já existe na query base (linha 80)
            query = query.filter(Colaborador.planta_id.in_(plantas_ids))

    # Executa a query (ordena por qualquer horário disponível)
    solicitacoes = query.order_by(
        db.func.coalesce(
            Solicitacao.horario_entrada,
            Solicitacao.horario_saida,
            Solicitacao.horario_desligamento
        )
    ).all()

    # Busca plantas do gerente (se aplicável)
    plantas_gerente = []
    if current_user.role == 'gerente':
        gerente = Gerente.query.filter_by(user_id=current_user.id).first()
        if gerente:
            plantas_gerente = gerente.plantas.all()

    # Calcula estatísticas
    total_solicitacoes = len(solicitacoes)
    blocos_distintos = len(
        set([s.colaborador.bloco_id for s in solicitacoes if s.colaborador.bloco_id]))
    passageiros_por_viagem = 3  # Configurável
    viagens_estimadas = (total_solicitacoes + passageiros_por_viagem -
                         1) // passageiros_por_viagem if total_solicitacoes > 0 else 0

    # Busca todos os blocos para o filtro
    todos_blocos = Bloco.query.filter_by(
        status='Ativo').order_by(Bloco.codigo_bloco).all()

    return render_template(
        'agrupamento.html',
        solicitacoes=solicitacoes,
        total_solicitacoes=total_solicitacoes,
        total_blocos_distintos=blocos_distintos,
        viagens_estimadas=viagens_estimadas,
        passageiros_por_viagem=passageiros_por_viagem,
        todos_blocos=todos_blocos,
        plantas_gerente=plantas_gerente,  # NOVO
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
        solicitacoes = Solicitacao.query.filter(
            Solicitacao.id.in_(solicitacoes_ids)).all()

        if len(solicitacoes) != len(solicitacoes_ids):
            return jsonify({'success': False, 'message': 'Algumas solicitações não foram encontradas'}), 404

        # Verifica se todas são do mesmo bloco (regra de negócio)
        blocos = set(
            [s.colaborador.bloco_id for s in solicitacoes if s.colaborador.bloco_id])
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

        # AUDITORIA: Registra criação de viagem manual
        log_viagem_audit(
            viagem_id=nova_viagem.id,
            action=AuditAction.VIAGEM_CRIADA,
            status_anterior=None,
            status_novo='Pendente',
            changes={
                'tipo': 'manual',
                'quantidade_solicitacoes': len(solicitacoes),
                'solicitacoes_ids': solicitacoes_ids
            }
        )

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
@permission_required(['admin', 'supervisor'])
def agrupar_automatico():
    """Agrupa automaticamente as solicitações pendentes usando algoritmo inteligente"""
    try:
        from app.agrupamento_algoritmo import gerar_sugestoes_agrupamento

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

        if current_user.role == 'supervisor':
            supervisor = Supervisor.query.filter_by(
                user_id=current_user.id).first()
            if supervisor:
                query = query.filter(
                    Solicitacao.supervisor_id == supervisor.id)

        # Ordena usando uma expressão CASE para pegar o horário correto
        horario_ordenacao = case(
            (Solicitacao.tipo_corrida == 'entrada', Solicitacao.horario_entrada),
            (Solicitacao.tipo_corrida == 'saida', Solicitacao.horario_saida),
            (Solicitacao.tipo_corrida == 'desligamento',
             db.func.coalesce(Solicitacao.horario_desligamento, Solicitacao.horario_saida)),
            else_=db.func.coalesce(
                Solicitacao.horario_entrada, Solicitacao.horario_saida, Solicitacao.horario_desligamento)
        )
        solicitacoes_pendentes = query.order_by(horario_ordenacao).all()

        if not solicitacoes_pendentes:
            flash('Nenhuma solicitação pendente encontrada para esta data', 'info')
            return redirect(url_for('admin.agrupamento'))

        # Busca configurações (se existirem)
        config_max_pass = Configuracao.query.filter_by(
            chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        config_janela = Configuracao.query.filter_by(
            chave='JANELA_TEMPO_AGRUPAMENTO_MIN').first()

        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        janela_tempo = int(config_janela.valor) if config_janela else 30

        # Executa o agrupamento usando o algoritmo inteligente V2
        from app.agrupamento_algoritmo import confirmar_agrupamento

        # Gera sugestões
        sugestoes = gerar_sugestoes_agrupamento(
            solicitacoes_pendentes,
            max_passageiros=max_passageiros,
            janela_tempo_minutos=janela_tempo
        )

        # Confirma e salva no banco
        resultado = confirmar_agrupamento(sugestoes, current_user.id)

        db.session.commit()

        # Monta mensagem detalhada
        mensagem = (
            f"[OK] Agrupamento concluído com sucesso!\n\n"
            f"[STATS] Estatísticas:\n"
            f"• {resultado['fretados_criados']} fretado(s) criado(s)\n"
            f"• {resultado['viagens_criadas']} viagem(ns) criada(s)\n"
            f"• {resultado['solicitacoes_agrupadas']} solicitação(ões) agrupada(s)"
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
@agrupamento_required
def gerar_sugestoes_agrupamento():
    """Gera sugestões de agrupamento sem salvar no banco"""
    try:
        from app.agrupamento_algoritmo import gerar_sugestoes_agrupamento
        from datetime import date
        import json

        data_filtro = request.args.get('data_filtro')
        if not data_filtro:
            data_filtro = date.today().strftime('%Y-%m-%d')

        tipo_corrida = request.args.get('tipo_corrida', '')
        bloco_id = request.args.get('bloco_id', '')
        status = request.args.get('status', 'Pendente')
        planta_id = request.args.get('planta_id', '')

        # Busca solicitações pendentes
        from sqlalchemy import func, or_
        from datetime import datetime as dt_module

        # Converte string de data para objeto date
        data_obj = dt_module.strptime(data_filtro, '%Y-%m-%d').date()

        query = Solicitacao.query.filter(
            Solicitacao.status == status,
            or_(
                func.date(Solicitacao.horario_entrada) == data_obj,
                func.date(Solicitacao.horario_saida) == data_obj,
                func.date(Solicitacao.horario_desligamento) == data_obj
            )
        )
        if tipo_corrida and tipo_corrida != 'Todos':
            query = query.filter(Solicitacao.tipo_corrida == tipo_corrida)

        if bloco_id and bloco_id != 'Todos':
            query = query.filter(Solicitacao.bloco_id == bloco_id)

        # Filtro adicional por perfil do usuário
        if current_user.role == 'gerente':
            gerente = Gerente.query.filter_by(user_id=current_user.id).first()
            if gerente:
                plantas_ids = [p.id for p in gerente.plantas.all()]
                query = query.join(Colaborador).filter(
                    Colaborador.planta_id.in_(plantas_ids))

        elif current_user.role == 'supervisor':
            supervisor = Supervisor.query.filter_by(
                user_id=current_user.id).first()
            if supervisor:
                query = query.filter(
                    Solicitacao.supervisor_id == supervisor.id)

        # Filtro por planta (opcional - apenas para Gerente)
        if planta_id and planta_id != 'Todos' and current_user.role == 'gerente':
            # Join com Colaborador já foi feito no filtro de Gerente acima (linha 407)
            query = query.filter(Colaborador.planta_id == int(planta_id))

        solicitacoes_pendentes = query.all()

        if not solicitacoes_pendentes:
            flash(
                'Nenhuma solicitação encontrada para os filtros selecionados.', 'warning')
            return redirect(url_for('admin.agrupamento'))

        # Busca configurações
        config_max_pass = Configuracao.query.filter_by(
            chave='max_passageiros_viagem').first()
        config_janela = Configuracao.query.filter_by(
            chave='janela_tempo_agrupamento').first()

        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3
        janela_tempo = int(config_janela.valor) if config_janela else 30

        # Gera sugestões usando o algoritmo V2
        sugestoes = gerar_sugestoes_agrupamento(
            solicitacoes_pendentes, max_passageiros, janela_tempo)

        # Extrai e serializa os dados do retorno
        fretados_raw = sugestoes.get('fretados', {})
        veiculos_raw = sugestoes.get('veiculos', {})
        resumo = sugestoes.get('resumo', {})

        # Serializa fretados
        fretados = {}
        for grupo_bloco, dados in fretados_raw.items():
            fretados[grupo_bloco] = {
                'sugestoes': [
                    {
                        'nome': sug.get('nome', ''),
                        'tipo_linha': sug.get('tipo_linha', ''),
                        'tipo_corrida': sug.get('tipo_corrida', ''),
                        'blocos': sug.get('blocos', []),
                        'quantidade': sug.get('quantidade', 0),
                        'solicitacoes': [serializar_solicitacao(s) for s in sug.get('solicitacoes', [])]
                    }
                    for sug in dados.get('sugestoes', [])
                ],
                'solicitacoes': [serializar_solicitacao(s) for s in dados.get('solicitacoes', [])]
            }

        # Serializa veículos
        veiculos = {}
        for grupo_bloco, grupos in veiculos_raw.items():
            veiculos[grupo_bloco] = [
                [serializar_solicitacao(s) for s in grupo]
                for grupo in grupos
            ]

        return render_template(
            'agrupamento_sugestoes.html',
            fretados=fretados,
            veiculos=veiculos,
            resumo=resumo,
            data_filtro=data_filtro
        )

    except Exception as e:
        flash(f'Erro ao gerar sugestões: {str(e)}', 'danger')
        return redirect(url_for('admin.agrupamento'))


@admin_bp.route('/finalizar_agrupamento', methods=['POST'])
@login_required
@agrupamento_required
def finalizar_agrupamento():
    """Finaliza o agrupamento criando viagens e fretados no banco de dados"""
    try:
        data = request.get_json()
        grupos = data.get('grupos', [])

        if not grupos:
            return jsonify({'success': False, 'message': 'Nenhum grupo para finalizar'}), 400

        viagens_criadas = 0
        fretados_criados = 0
        solicitacoes_agrupadas = 0
        viagens_ids_para_notificar = []  # [OK] NOVA: Lista para armazenar IDs das viagens

        # [FIX] CORREÇÃO: Força reload de todos os objetos da sessão para evitar objetos desatualizados
        db.session.expire_all()
        logger.info("[RETRY] Sessão do banco de dados limpa antes do agrupamento")

        for grupo in grupos:
            if not grupo or not isinstance(grupo, dict):
                continue

            tipo_grupo = grupo.get('tipo', 'veiculo')
            grupo_ids = grupo.get('solicitacoes', [])

            if not grupo_ids:
                continue

            # Busca as solicitações do grupo
            # [FIX] NOTA: NÃO usamos with_for_update() porque é incompatível com joinedload() (LEFT OUTER JOIN)
            # Proteção contra duplicação é feita via: expire_all() + validação de status + flush()
            solicitacoes = Solicitacao.query.options(
                joinedload(Solicitacao.colaborador).joinedload(
                    Colaborador.bloco)
            ).filter(Solicitacao.id.in_(grupo_ids)).all()

            if not solicitacoes:
                logger.warning(
                    f"[AVISO]  Nenhuma solicitação encontrada para IDs: {grupo_ids}")
                continue

            logger.info(
                f"[INFO] Processando {len(solicitacoes)} solicitação(ões): IDs {grupo_ids}")

            # Pega dados da primeira solicitação (todas do grupo têm os mesmos dados base)
            primeira = solicitacoes[0]

            # Coleta IDs dos colaboradores em formato JSON
            import json
            colaboradores_ids = [sol.colaborador_id for sol in solicitacoes]
            colaboradores_json = json.dumps(colaboradores_ids)

            # Coleta blocos únicos do grupo (por ID)
            blocos_unicos_ids = list(
                set([sol.bloco_id for sol in solicitacoes if sol.bloco_id]))
            bloco_principal = blocos_unicos_ids[0] if blocos_unicos_ids else None
            blocos_ids_str = ','.join(
                map(str, blocos_unicos_ids)) if blocos_unicos_ids else None

            # [OK] CORREÇÃO: Coleta GRUPOS de blocos únicos (prefixo antes do ponto)
            # Exemplo: CPV2.1 e CPV2.5 → ambos são do grupo "CPV2"
            grupos_blocos_unicos = set()
            for sol in solicitacoes:
                if sol.colaborador and sol.colaborador.bloco:
                    codigo_bloco = sol.colaborador.bloco.codigo_bloco  # Ex: "CPV2.1"
                    if codigo_bloco:
                        # Pega o prefixo antes do ponto (CPV2.1 → CPV2)
                        grupo_bloco = codigo_bloco.split(
                            '.')[0] if '.' in codigo_bloco else codigo_bloco
                        grupos_blocos_unicos.add(grupo_bloco)

            grupos_blocos_unicos = list(grupos_blocos_unicos)
            mesmo_grupo_bloco = len(grupos_blocos_unicos) == 1

            # REGRA: Pega o MAIOR valor entre as solicitações (não soma)
            valores = [
                sol.valor for sol in solicitacoes if sol.valor is not None]
            repasses = [
                sol.valor_repasse for sol in solicitacoes if sol.valor_repasse is not None]

            valor_grupo = max(valores) if valores else None
            repasse_grupo = max(repasses) if repasses else None

            # Determina horários e tipo baseado no tipo de corrida (com normalização)
            tipo_normalizado = primeira.tipo_corrida.lower().strip()
            tipo_normalizado = tipo_normalizado.replace(
                'ã', 'a').replace('á', 'a').replace('í', 'i')

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

            # [DEBUG] DEBUG: Log para diagnóstico
            logger.info(
                f"[DEBUG] DEBUG FRETADO: len(solicitacoes)={len(solicitacoes)}, grupos_blocos_unicos={grupos_blocos_unicos}, mesmo_grupo_bloco={mesmo_grupo_bloco}")

            # REGRA: Se 10+ passageiros do mesmo GRUPO DE BLOCO, cria FRETADO; senão, cria VIAGEM
            # Exemplo: CPV2.1 + CPV2.5 = mesmo grupo (CPV2) → pode criar fretado
            if len(solicitacoes) >= 10 and mesmo_grupo_bloco:
                logger.info(
                    f"[OK] CRIANDO FRETADO: {len(solicitacoes)} passageiros do grupo {grupos_blocos_unicos[0]}")
                # Cria 1 registro de FRETADO para CADA colaborador
                try:
                    for solicitacao in solicitacoes:
                        colaborador = solicitacao.colaborador

                        # Pega dados do colaborador
                        nome_colaborador = colaborador.nome if colaborador else 'Sem nome'
                        matricula = colaborador.matricula if colaborador else None
                        telefone = colaborador.telefone if colaborador else None
                        endereco = colaborador.endereco if colaborador else None
                        bairro = colaborador.bairro if colaborador else None
                        cidade = colaborador.cidade if colaborador else None

                        # Determina horários baseado no tipo de corrida
                        tipo_normalizado = solicitacao.tipo_corrida.lower().strip()
                        tipo_normalizado = tipo_normalizado.replace(
                            'ã', 'a').replace('á', 'a').replace('í', 'i')

                        if 'entrada' in tipo_normalizado and 'saida' not in tipo_normalizado:
                            horario_entrada = solicitacao.horario_entrada
                            horario_saida = None
                            horario_desligamento = None
                        elif 'saida' in tipo_normalizado and 'entrada' not in tipo_normalizado:
                            horario_entrada = None
                            horario_saida = solicitacao.horario_saida
                            horario_desligamento = None
                        elif 'desligamento' in tipo_normalizado:
                            horario_entrada = None
                            horario_saida = None
                            horario_desligamento = solicitacao.horario_desligamento
                        else:
                            horario_entrada = solicitacao.horario_entrada
                            horario_saida = solicitacao.horario_saida
                            horario_desligamento = None

                        # Cria o registro de fretado para este colaborador
                        novo_fretado = Fretado(
                            # Referências
                            solicitacao_id=solicitacao.id,
                            colaborador_id=solicitacao.colaborador_id,

                            # Dados do colaborador
                            nome_colaborador=nome_colaborador,
                            matricula=matricula,
                            telefone=telefone,

                            # Endereço do colaborador
                            endereco=endereco,
                            bairro=bairro,
                            cidade=cidade,

                            # Localização e contexto
                            empresa_id=solicitacao.empresa_id,
                            planta_id=solicitacao.planta_id,
                            bloco_id=solicitacao.colaborador.bloco_id if colaborador else None,
                            grupo_bloco=grupos_blocos_unicos[0] if grupos_blocos_unicos else None,

                            # Tipo de viagem
                            tipo_linha='FIXA',
                            tipo_corrida=solicitacao.tipo_corrida,

                            # Horários
                            horario_entrada=horario_entrada,
                            horario_saida=horario_saida,
                            horario_desligamento=horario_desligamento,

                            # Status e controle
                            status='Fretado',
                            observacoes=f'Fretado criado automaticamente via agrupamento',

                            # Auditoria
                            created_by_user_id=current_user.id,
                            data_criacao=datetime.utcnow(),
                            data_atualizacao=datetime.utcnow()
                        )

                        db.session.add(novo_fretado)
                        db.session.flush()  # Para obter o ID

                    # [OK] CORREÇÃO V3: Atualiza fretados com VALIDAÇÃO
                    solicitacoes_ids_fretado = []
                    for solicitacao in solicitacoes:
                        if solicitacao.status == 'Fretado':
                            logger.warning(
                                f"[AVISO]  Solicitação #{solicitacao.id} já estava com status Fretado")
                            continue
                        solicitacoes_ids_fretado.append(solicitacao.id)
                    
                    if solicitacoes_ids_fretado:
                        logger.info(f"[>>>] Atualizando {len(solicitacoes_ids_fretado)} solicitações para Fretado")
                        
                        # UPDATE em massa
                        quantidade_fretado = Solicitacao.query.filter(
                            Solicitacao.id.in_(solicitacoes_ids_fretado)
                        ).update({
                            'status': 'Fretado'
                        }, synchronize_session='fetch')
                        
                        logger.info(f"[...] UPDATE fretado retornou: {quantidade_fretado} registro(s)")
                        
                        # Flush
                        db.session.flush()
                        logger.info(f"[SAVE] Flush executado para fretado")
                        
                        # VALIDAÇÃO
                        solicitacoes_verif_fretado = Solicitacao.query.filter(
                            Solicitacao.id.in_(solicitacoes_ids_fretado)
                        ).all()
                        
                        nao_fretadas = []
                        for sol in solicitacoes_verif_fretado:
                            if sol.status != 'Fretado':
                                nao_fretadas.append(sol.id)
                        
                        # RETRY se necessário
                        if nao_fretadas:
                            logger.warning(f"[AVISO]  {len(nao_fretadas)} solicitações não foram fretadas, tentando retry...")
                            for sol_id in nao_fretadas:
                                sol = Solicitacao.query.get(sol_id)
                                if sol:
                                    sol.status = 'Fretado'
                                    logger.info(f"[OK] Solicitação #{sol_id} fretada manualmente")
                            db.session.flush()
                        
                        solicitacoes_agrupadas += len(solicitacoes_ids_fretado)
                        logger.info(f"[OK] {len(solicitacoes_ids_fretado)} solicitações atualizadas para Fretado")

                except Exception as e:
                    logger.error(
                        f"[ERRO] ERRO ao criar fretado para grupo {grupos_blocos_unicos[0]}: {e}")
                    raise  # Re-lança exceção para forçar rollback

                fretados_criados += 1  # Conta como 1 grupo de fretado criado
                logger.info(
                    f"[SUCCESS] FRETADO CRIADO: {len(solicitacoes)} registros na tabela fretado para o grupo {grupos_blocos_unicos[0] if grupos_blocos_unicos else 'N/A'}")
            else:
                logger.info(
                    f"[AVISO] CRIANDO VIAGEM: len={len(solicitacoes)}, mesmo_grupo={mesmo_grupo_bloco}")
                # Cria VIAGEM
                nova_viagem = Viagem(
                    # Status
                    status='Pendente',

                    # Localização
                    empresa_id=primeira.empresa_id,
                    planta_id=primeira.planta_id,
                    bloco_id=bloco_principal,
                    blocos_ids=blocos_ids_str,

                    # Tipo de viagem
                    tipo_linha=primeira.tipo_linha if hasattr(
                        primeira, 'tipo_linha') else 'FIXA',
                    tipo_corrida=tipo_normalizado,

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
                    valor=valor_grupo,
                    valor_repasse=repasse_grupo,

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
                db.session.flush()

                # [FIX] CORREÇÃO DEFINITIVA: Usa UPDATE em massa ao invés de atualizar objeto por objeto
                # Isso evita problemas com expire_all() e garante que o status seja atualizado corretamente
                try:
                    # Coleta IDs das solicitações que ainda não estão agrupadas
                    solicitacoes_ids_para_agrupar = []
                    for solicitacao in solicitacoes:
                        # Verifica se já está agrupada (evita duplicação)
                        if solicitacao.status == 'Agrupada' and solicitacao.viagem_id:
                            logger.warning(
                                f"[AVISO]  Solicitação #{solicitacao.id} já estava agrupada na viagem #{solicitacao.viagem_id}")
                            continue
                        solicitacoes_ids_para_agrupar.append(solicitacao.id)

                    # [OK] CORREÇÃO V3: Atualiza com VALIDAÇÃO e RETRY
                    if solicitacoes_ids_para_agrupar:
                        logger.info(f"[>>>] Tentando atualizar {len(solicitacoes_ids_para_agrupar)} solicitações: {solicitacoes_ids_para_agrupar}")
                        
                        # TENTATIVA 1: UPDATE em massa
                        quantidade_atualizada = Solicitacao.query.filter(
                            Solicitacao.id.in_(solicitacoes_ids_para_agrupar)
                        ).update({
                            'viagem_id': nova_viagem.id,
                            'status': 'Agrupada'
                        }, synchronize_session='fetch')
                        
                        logger.info(f"[...] UPDATE em massa retornou: {quantidade_atualizada} registro(s)")
                        
                        # Força flush para persistir
                        db.session.flush()
                        logger.info(f"[SAVE] Flush executado")
                        
                        # VALIDAÇÃO: Verifica se TODAS foram atualizadas
                        solicitacoes_verificacao = Solicitacao.query.filter(
                            Solicitacao.id.in_(solicitacoes_ids_para_agrupar)
                        ).all()
                        
                        nao_atualizadas = []
                        for sol in solicitacoes_verificacao:
                            if sol.status != 'Agrupada' or sol.viagem_id != nova_viagem.id:
                                nao_atualizadas.append(sol.id)
                        
                        # Se houver solicitações não atualizadas, RETRY objeto por objeto
                        if nao_atualizadas:
                            logger.warning(f"[AVISO]  UPDATE em massa falhou para {len(nao_atualizadas)} solicitações: {nao_atualizadas}")
                            logger.info(f"[RETRY] Tentando RETRY objeto por objeto...")
                            
                            for sol_id in nao_atualizadas:
                                sol = Solicitacao.query.get(sol_id)
                                if sol:
                                    sol.viagem_id = nova_viagem.id
                                    sol.status = 'Agrupada'
                                    logger.info(f"[OK] Solicitação #{sol_id} atualizada manualmente")
                            
                            # Flush após retry
                            db.session.flush()
                            logger.info(f"[SAVE] Flush executado após retry")
                            
                            # VALIDAÇÃO FINAL
                            solicitacoes_final = Solicitacao.query.filter(
                                Solicitacao.id.in_(solicitacoes_ids_para_agrupar)
                            ).all()
                            
                            ainda_nao_atualizadas = []
                            for sol in solicitacoes_final:
                                if sol.status != 'Agrupada' or sol.viagem_id != nova_viagem.id:
                                    ainda_nao_atualizadas.append(sol.id)
                            
                            if ainda_nao_atualizadas:
                                logger.error(f"[ERRO] FALHA CRÍTICA: {len(ainda_nao_atualizadas)} solicitações AINDA não foram atualizadas: {ainda_nao_atualizadas}")
                                raise Exception(f"Falha ao atualizar solicitações: {ainda_nao_atualizadas}")
                            else:
                                logger.info(f"[OK] RETRY bem-sucedido! Todas as {len(solicitacoes_ids_para_agrupar)} solicitações foram atualizadas")
                        else:
                            logger.info(f"[OK] SUCESSO: Todas as {len(solicitacoes_ids_para_agrupar)} solicitações foram atualizadas corretamente")
                        
                        solicitacoes_agrupadas += len(solicitacoes_ids_para_agrupar)

                except Exception as e:
                    logger.error(
                        f"[ERRO] ERRO ao atualizar solicitações da viagem #{nova_viagem.id}: {e}")
                    raise  # Re-lança exceção para forçar rollback

                viagens_criadas += 1
                # [OK] NOVA: Armazena ID para notificar depois
                viagens_ids_para_notificar.append(nova_viagem.id)

        # [FIX] CORREÇÃO: Commit final com log de confirmação
        db.session.commit()
        logger.info(
            f"[OK] COMMIT REALIZADO: {viagens_criadas} viagem(ns), {fretados_criados} fretado(s), {solicitacoes_agrupadas} solicitação(ões) agrupada(s)")

        # [OK] NOVA: Envia notificações WhatsApp em background (assíncrono)
        if viagens_ids_para_notificar:
            import threading
            from flask import current_app

            # [OK] Captura o app ANTES de criar a thread
            app = current_app._get_current_object()

            def enviar_notificacoes():
                """Worker thread que cria sua própria sessão do banco de dados"""
                from app import db as db_module
                from app.models import Viagem
                from sqlalchemy.orm import scoped_session, sessionmaker

                # Usa o contexto da aplicação (app capturado antes da thread)
                with app.app_context():
                    # Cria nova sessão para esta thread
                    session_factory = sessionmaker(bind=db_module.engine)
                    Session = scoped_session(session_factory)
                    session_local = Session()  # Retorna Session

                    try:
                        # [OK] OTIMIZAÇÃO: Envia 1 mensagem única por motorista (em lote)
                        # Ao invés de enviar 1 mensagem para cada viagem criada
                        quantidade_viagens = len(viagens_ids_para_notificar)

                        enviadas = notification_service.notificar_novas_viagens_em_lote(
                            quantidade_viagens=quantidade_viagens
                        )

                        if enviadas > 0:
                            logger.info(
                                f"[OK] {enviadas} motorista(s) notificado(s) sobre {quantidade_viagens} nova(s) viagem(ns)")
                        else:
                            logger.warning(
                                f"[AVISO]  Nenhum motorista notificado sobre as {quantidade_viagens} viagem(ns) criadas")

                    except Exception as e:
                        logger.error(
                            f"[ERRO] Erro ao enviar notificações em lote: {e}")

                    finally:
                        # Fecha a sessão da thread
                        session_local.close()   # [OK] Fecha a sessão
                        Session.remove()        # [OK] Remove do registry do scoped_session

            # Inicia thread em background
            thread = threading.Thread(target=enviar_notificacoes, daemon=True)
            thread.start()
            logger.info(
                f"[>>>] Iniciando envio de notificação em lote sobre {len(viagens_ids_para_notificar)} viagem(ns) criada(s)...")

        # Limpa a sessão
        from flask import session
        session.pop('grupos_sugeridos', None)
        session.pop('data_agrupamento', None)

        mensagem = f'[OK] Agrupamento finalizado com sucesso!'
        if fretados_criados > 0:
            mensagem += f' {fretados_criados} fretado(s) criado(s).'
        if viagens_criadas > 0:
            mensagem += f' {viagens_criadas} viagem(ns) criada(s).'
        mensagem += f' Total: {solicitacoes_agrupadas} solicitação(ões) agrupada(s).'

        if viagens_ids_para_notificar:
            mensagem += f' Notificações WhatsApp sendo enviadas em background.'

        return jsonify({
            'success': True,
            'message': mensagem,
            'viagens_criadas': viagens_criadas,
            'fretados_criados': fretados_criados,
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
        config_max_pass = Configuracao.query.filter_by(
            chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
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
        config_max_pass = Configuracao.query.filter_by(
            chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        max_passageiros = int(config_max_pass.valor) if config_max_pass else 3

        # Verifica se a mesclagem não excede o limite
        total_passageiros = len(
            grupos[grupo_index_1]) + len(grupos[grupo_index_2])
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
