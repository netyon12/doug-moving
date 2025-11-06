"""
Módulo de Solicitações
======================

CRUD de solicitações e exportação.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func, or_
from io import StringIO
import io
import csv
import logging
from datetime import datetime, date

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp

# IMPORTAR SISTEMA DE AUDITORIA
from ..utils.admin_audit import log_audit, AuditAction

logger = logging.getLogger(__name__)
# No início do arquivo
logger.info("Módulo solicitacoes carregado")


@admin_bp.route('/solicitacoes')
@login_required
@permission_required(['admin', 'gerente', 'supervisor'])
def solicitacoes():
    # --- LÓGICA DE FILTRAGEM ---
    query = Solicitacao.query

    # Filtro por perfil
    if current_user.role == 'gerente':
        ids_supervisores = [s.id for s in Supervisor.query.filter_by(
            gerente_id=current_user.gerente.id)]
        query = query.filter(Solicitacao.supervisor_id.in_(ids_supervisores))
    elif current_user.role == 'supervisor':
        query = query.filter(Solicitacao.supervisor_id ==
                             current_user.supervisor.id)

    # Filtros do formulário
    filtros = request.args

 # ===== FILTRO PADRÃO DO MÊS ATUAL =====
    if not filtros.get('data_inicio') and not filtros.get('data_fim'):
        hoje = date.today()
        primeiro_dia_mes = date(hoje.year, hoje.month, 1)

        # Calcula o último dia do mês
        if hoje.month == 12:
            ultimo_dia_mes = date(hoje.year, 12, 31)
        else:
            proximo_mes = date(hoje.year, hoje.month + 1, 1)
            from datetime import timedelta
            ultimo_dia_mes = proximo_mes - timedelta(days=1)

        # Cria um dicionário mutável com os filtros padrão
        filtros_dict = dict(filtros)
        filtros_dict['data_inicio'] = primeiro_dia_mes.strftime('%Y-%m-%d')
        filtros_dict['data_fim'] = ultimo_dia_mes.strftime('%Y-%m-%d')

        # Atualiza a variável filtros
        from werkzeug.datastructures import ImmutableMultiDict
        filtros = ImmutableMultiDict(filtros_dict)
    # ===== FIM =====

    # NOVOS FILTROS - ID da Solicitação
    if filtros.get('id_solicitacao'):
        query = query.filter(Solicitacao.id == filtros.get('id_solicitacao'))

    # NOVOS FILTROS - Nome do Colaborador
    if filtros.get('colaborador_nome'):
        query = query.join(Colaborador).filter(
            Colaborador.nome.ilike(f"%{filtros.get('colaborador_nome')}%"))

    # NOVOS FILTROS - Matrícula do Colaborador
    if filtros.get('colaborador_matricula'):
        query = query.join(Colaborador).filter(
            Colaborador.matricula.ilike(f"%{filtros.get('colaborador_matricula')}%"))

    # Filtro por tipo de corrida
    if filtros.get('tipo_corrida'):
        query = query.filter(Solicitacao.tipo_corrida ==
                             filtros.get('tipo_corrida'))

    # Filtros de data (considera o tipo de corrida)
    tipo_corrida = filtros.get('tipo_corrida', '').lower()

    if filtros.get('data_inicio'):
        data_inicio = datetime.strptime(filtros.get('data_inicio'), '%Y-%m-%d')

        if tipo_corrida == 'entrada' or tipo_corrida == 'entrada_saida':
            query = query.filter(Solicitacao.horario_entrada >= data_inicio)
        elif tipo_corrida == 'saida' or tipo_corrida == 'saída':
            query = query.filter(Solicitacao.horario_saida >= data_inicio)
        elif tipo_corrida == 'desligamento':
            query = query.filter(
                Solicitacao.horario_desligamento >= data_inicio)
        else:
            # Sem tipo especificado: busca em todos os campos
            query = query.filter(
                or_(
                    Solicitacao.horario_entrada >= data_inicio,
                    Solicitacao.horario_saida >= data_inicio,
                    Solicitacao.horario_desligamento >= data_inicio
                )
            )

    if filtros.get('data_fim'):
        data_fim = datetime.strptime(filtros.get('data_fim'), '%Y-%m-%d')
        data_fim = data_fim.replace(hour=23, minute=59, second=59)

        if tipo_corrida == 'entrada' or tipo_corrida == 'entrada_saida':
            query = query.filter(Solicitacao.horario_entrada <= data_fim)
        elif tipo_corrida == 'saida' or tipo_corrida == 'saída':
            query = query.filter(Solicitacao.horario_saida <= data_fim)
        elif tipo_corrida == 'desligamento':
            query = query.filter(Solicitacao.horario_desligamento <= data_fim)
        else:
            # Sem tipo especificado: busca em todos os campos
            query = query.filter(
                or_(
                    Solicitacao.horario_entrada <= data_fim,
                    Solicitacao.horario_saida <= data_fim,
                    Solicitacao.horario_desligamento <= data_fim
                )
            )

    # Outros filtros
    if filtros.get('viagem_id'):
        query = query.filter(Solicitacao.viagem_id == filtros.get('viagem_id'))
    if filtros.get('status'):
        query = query.filter(Solicitacao.status == filtros.get('status'))
    if filtros.get('supervisor_id'):
        query = query.filter(Solicitacao.supervisor_id ==
                             filtros.get('supervisor_id'))
    if filtros.get('planta'):
        # Requer join com Colaborador e Planta
        query = query.join(Colaborador).join(Planta).filter(
            Planta.nome.ilike(f"%{filtros.get('planta')}%"))
    if filtros.get('bloco_id'):
        # Requer join com Colaborador
        query = query.join(Colaborador).filter(
            Colaborador.bloco_id == filtros.get('bloco_id'))

    solicitacoes = query.order_by(Solicitacao.id.desc()).all()

    # --- DADOS PARA OS DROPDOWNS DOS FILTROS ---
    if current_user.role == 'admin':
        supervisores_filtro = Supervisor.query.order_by(Supervisor.nome).all()
        blocos_filtro = Bloco.query.order_by(Bloco.codigo_bloco).all()
    elif current_user.role == 'gerente':
        supervisores_filtro = Supervisor.query.filter_by(
            gerente_id=current_user.gerente.id).order_by(Supervisor.nome).all()
        blocos_filtro = Bloco.query.join(Empresa).filter(
            Empresa.id == current_user.empresa.id).order_by(Bloco.codigo_bloco).all()
    else:  # Supervisor
        supervisores_filtro = [current_user.supervisor]
        blocos_filtro = Bloco.query.join(Empresa).filter(
            Empresa.id == current_user.empresa.id).order_by(Bloco.codigo_bloco).all()

    # Retorna o template com as variáveis corretas
    return render_template(
        'solicitacoes.html',
        solicitacoes=solicitacoes,
        todos_supervisores=supervisores_filtro,
        todos_blocos=blocos_filtro,
        filtros=filtros
    )


@admin_bp.route('/nova_solicitacao', methods=['GET', 'POST'])
@login_required
# Permissão atualizada para incluir 'admin' e 'gerente'
@permission_required(['supervisor', 'admin', 'gerente'])
def nova_solicitacao():

    if request.method == 'POST':
        logger.debug(f"Nova solicitação recebida: {request.form}")
        try:
            # NOVA VALIDAÇÃO: Verifica se há datas no passado
            from datetime import date
            hoje = date.today()

            horarios_entrada = request.form.getlist('horario_entrada[]')
            horarios_saida = request.form.getlist('horario_saida[]')
            horarios_desligamento = request.form.getlist(
                'horario_desligamento[]')

            # Valida todas as datas
            for horario in horarios_entrada + horarios_saida + horarios_desligamento:
                if horario:
                    data_horario = datetime.strptime(
                        horario, '%Y-%m-%dT%H:%M').date()
                    if data_horario < hoje:
                        flash(
                            'Não é permitido criar solicitações com data no passado.', 'danger')
                        return redirect(url_for('admin.nova_solicitacao'))

            # Obtém o tipo de corrida e normaliza (lowercase, sem acentos)
            tipo_corrida = request.form.get('tipo_corrida')
            if not tipo_corrida:
                flash('Tipo de corrida não especificado.', 'warning')
                return redirect(url_for('admin.nova_solicitacao'))

            # Normalização: lowercase e remove acentos
            tipo_corrida = tipo_corrida.lower().strip()
            tipo_corrida = tipo_corrida.replace(
                'ã', 'a').replace('á', 'a').replace('í', 'i')

            # Valida valores permitidos
            tipos_permitidos = ['entrada', 'saida',
                                'entrada_saida', 'desligamento']
            if tipo_corrida not in tipos_permitidos:
                flash(f'Tipo de corrida inválido: {tipo_corrida}', 'danger')
                return redirect(url_for('admin.nova_solicitacao'))

            # Obtém os dados do formulário (com [] no nome)
            colaborador_ids = request.form.getlist('colaborador_id[]')
            horarios_entrada = request.form.getlist('horario_entrada[]')
            horarios_saida = request.form.getlist('horario_saida[]')
            horarios_desligamento = request.form.getlist(
                'horario_desligamento[]')
            turnos_entrada = request.form.getlist('turno_entrada[]')
            turnos_saida = request.form.getlist('turno_saida[]')
            turnos_desligamento = request.form.getlist('turno_desligamento[]')

            # Validação básica
            if not colaborador_ids:
                flash('É necessário adicionar pelo menos um colaborador.', 'warning')
                return redirect(url_for('admin.nova_solicitacao'))

            # Determina empresa, planta e supervisor
            if current_user.role == 'supervisor':
                supervisor_id = current_user.supervisor.id
                empresa_id = current_user.supervisor.empresa_id
                # Se supervisor tem múltiplas plantas, pega do formulário
                planta_id = request.form.get('planta_id')
                if not planta_id and current_user.supervisor.plantas:
                    planta_id = current_user.supervisor.plantas[0].id
                # Valida se planta pertence ao supervisor
                planta_ids_supervisor = [
                    p.id for p in current_user.supervisor.plantas]
                if planta_id and int(planta_id) not in planta_ids_supervisor:
                    flash('Planta inválida para este supervisor.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))
            elif current_user.role == 'admin':
                # Admin precisa especificar empresa e planta
                empresa_id = request.form.get('empresa_id')
                planta_id = request.form.get('planta_id')

                if not empresa_id or not planta_id:
                    flash('Empresa e Planta devem ser especificadas.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))

                # Busca supervisor da planta (pega o primeiro que tem essa planta)
                supervisor = Supervisor.query.join(
                    Supervisor.plantas).filter(Planta.id == planta_id).first()
                if not supervisor:
                    flash('Nenhum supervisor encontrado para esta planta.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))
                supervisor_id = supervisor.id
            elif current_user.role == 'gerente':
                # Gerente funciona similar ao supervisor
                planta_id = request.form.get('planta_id')

                if not planta_id:
                    flash('Planta deve ser especificada.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))

                # Busca a planta para obter empresa_id
                planta = Planta.query.get(planta_id)
                if not planta:
                    flash('Planta inválida.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))

                empresa_id = planta.empresa_id

                # Busca supervisor da planta que pertence ao gerente
                supervisor = Supervisor.query.join(
                    Supervisor.plantas).filter(
                        Planta.id == planta_id,
                        Supervisor.gerente_id == current_user.gerente.id
                ).first()

                if not supervisor:
                    flash('Nenhum supervisor encontrado para esta planta.', 'danger')
                    return redirect(url_for('admin.nova_solicitacao'))

                supervisor_id = supervisor.id
            else:
                flash('Permissão negada.', 'danger')
                return redirect(url_for('home'))

            # Função auxiliar para buscar ID do turno pelo nome
            def buscar_turno_id(nome_turno, planta_id):
                if not nome_turno or nome_turno == 'Não definido':
                    return None
                turno = Turno.query.filter_by(
                    nome=nome_turno, planta_id=planta_id).first()
                return turno.id if turno else None

            # Função auxiliar para buscar valor baseado em bloco e turno
            def buscar_valores(bloco_id, turno_id):
                if not bloco_id or not turno_id:
                    return None, None

                bloco = Bloco.query.get(bloco_id)
                turno = Turno.query.get(turno_id)

                if not bloco or not turno:
                    return None, None

                valor = bloco.get_valor_por_turno(turno)
                repasse = bloco.get_repasse_por_turno(turno)

                return float(valor) if valor else None, float(repasse) if repasse else None

            # Cria as solicitações
            solicitacoes_criadas = 0
            solicitacoes_ids_criadas = []  # Para auditoria
            solicitacoes_duplicadas = []

            for i, colab_id in enumerate(colaborador_ids):
                # Verifica se o colaborador existe
                colaborador = Colaborador.query.get(colab_id)
                if not colaborador:
                    continue

                # Obtém o ID do usuário logado
                user_id = current_user.id if current_user.is_authenticated else None

                dados_solicitacao = {
                    'colaborador_id': colab_id,
                    'supervisor_id': supervisor_id,
                    'empresa_id': empresa_id,
                    'planta_id': planta_id,
                    'bloco_id': colaborador.bloco_id,
                    'tipo_linha': 'EXTRA',  # Por enquanto sempre EXTRA
                    'tipo_corrida': tipo_corrida,
                    'status': 'Pendente',
                    'created_by_user_id': user_id  # Quem criou a solicitação
                }

                # Adiciona horários e turnos baseado no tipo de corrida
                turno_principal_id = None  # Para calcular o valor

                if tipo_corrida == 'entrada':
                    if i < len(horarios_entrada) and horarios_entrada[i]:
                        dados_solicitacao['horario_entrada'] = datetime.strptime(
                            horarios_entrada[i], '%Y-%m-%dT%H:%M')
                        if i < len(turnos_entrada):
                            dados_solicitacao['turno_entrada_id'] = buscar_turno_id(
                                turnos_entrada[i], planta_id)
                            turno_principal_id = dados_solicitacao['turno_entrada_id']

                elif tipo_corrida == 'saida':
                    if i < len(horarios_saida) and horarios_saida[i]:
                        dados_solicitacao['horario_saida'] = datetime.strptime(
                            horarios_saida[i], '%Y-%m-%dT%H:%M')
                        if i < len(turnos_saida):
                            dados_solicitacao['turno_saida_id'] = buscar_turno_id(
                                turnos_saida[i], planta_id)
                            turno_principal_id = dados_solicitacao['turno_saida_id']

                elif tipo_corrida == 'entrada_saida':
                    # CORRIGIDO: Cria 2 solicitações separadas (uma de entrada e outra de saída)

                    # 1. Cria solicitação de ENTRADA
                    if i < len(horarios_entrada) and horarios_entrada[i]:
                        dados_entrada = dados_solicitacao.copy()
                        dados_entrada['tipo_corrida'] = 'entrada'
                        dados_entrada['horario_entrada'] = datetime.strptime(
                            horarios_entrada[i], '%Y-%m-%dT%H:%M')

                        if i < len(turnos_entrada):
                            turno_entrada_id = buscar_turno_id(
                                turnos_entrada[i], planta_id)
                            dados_entrada['turno_entrada_id'] = turno_entrada_id

                            # Calcula valores para entrada
                            valor, repasse = buscar_valores(
                                colaborador.bloco_id, turno_entrada_id)
                            if valor:
                                dados_entrada['valor'] = valor
                            if repasse:
                                dados_entrada['valor_repasse'] = repasse

                        # Validação de duplicação para entrada
                        data_entrada = dados_entrada['horario_entrada'].date()
                        entrada_existente = Solicitacao.query.filter(
                            Solicitacao.colaborador_id == colab_id,
                            Solicitacao.tipo_corrida == 'entrada',
                            db.func.date(
                                Solicitacao.horario_entrada) == data_entrada,
                            Solicitacao.status != 'Cancelada'
                        ).first()

                        if not entrada_existente:
                            solicitacao_entrada = Solicitacao(**dados_entrada)
                            db.session.add(solicitacao_entrada)
                            db.session.flush()  # Para obter o ID
                            solicitacoes_ids_criadas.append(
                                solicitacao_entrada.id)
                            solicitacoes_criadas += 1
                        else:
                            solicitacoes_duplicadas.append(
                                f"{colaborador.nome} (entrada)")

                    # 2. Cria solicitação de SAÍDA
                    if i < len(horarios_saida) and horarios_saida[i]:
                        dados_saida = dados_solicitacao.copy()
                        dados_saida['tipo_corrida'] = 'saida'
                        dados_saida['horario_saida'] = datetime.strptime(
                            horarios_saida[i], '%Y-%m-%dT%H:%M')

                        if i < len(turnos_saida):
                            turno_saida_id = buscar_turno_id(
                                turnos_saida[i], planta_id)
                            dados_saida['turno_saida_id'] = turno_saida_id

                            # Calcula valores para saída
                            valor, repasse = buscar_valores(
                                colaborador.bloco_id, turno_saida_id)
                            if valor:
                                dados_saida['valor'] = valor
                            if repasse:
                                dados_saida['valor_repasse'] = repasse

                        # Validação de duplicação para saída
                        data_saida = dados_saida['horario_saida'].date()
                        saida_existente = Solicitacao.query.filter(
                            Solicitacao.colaborador_id == colab_id,
                            Solicitacao.tipo_corrida == 'saida',
                            db.func.date(
                                Solicitacao.horario_saida) == data_saida,
                            Solicitacao.status != 'Cancelada'
                        ).first()

                        if not saida_existente:
                            solicitacao_saida = Solicitacao(**dados_saida)
                            db.session.add(solicitacao_saida)
                            db.session.flush()  # Para obter o ID
                            solicitacoes_ids_criadas.append(
                                solicitacao_saida.id)
                            solicitacoes_criadas += 1
                        else:
                            solicitacoes_duplicadas.append(
                                f"{colaborador.nome} (saída)")

                    # Pula para o próximo colaborador (não executa a lógica padrão de criação)
                    continue

                elif tipo_corrida == 'desligamento':
                    if i < len(horarios_desligamento) and horarios_desligamento[i]:
                        dados_solicitacao['horario_desligamento'] = datetime.strptime(
                            horarios_desligamento[i], '%Y-%m-%dT%H:%M')
                        if i < len(turnos_desligamento):
                            dados_solicitacao['turno_desligamento_id'] = buscar_turno_id(
                                turnos_desligamento[i], planta_id)
                            turno_principal_id = dados_solicitacao['turno_desligamento_id']

                # Validação de duplicação - CORRIGIDA para permitir entrada E saída no mesmo dia
                # Se tirar os comentários, nao vai permitir duas ou mais entradas ou saidas no mesmo dia. Comentado deixa criar.
                # solicitacao_duplicada = False

                # if tipo_corrida == 'entrada' and dados_solicitacao.get('horario_entrada'):
                #    data_entrada = dados_solicitacao['horario_entrada'].date()
                #    entrada_existente = Solicitacao.query.filter(
                #        Solicitacao.colaborador_id == colab_id,
                #        Solicitacao.tipo_corrida == 'entrada',
                #        db.func.date(Solicitacao.horario_entrada) == data_entrada,
                #        Solicitacao.status != 'Cancelada'
                #    ).first()

                #    if entrada_existente:
                #        solicitacoes_duplicadas.append(f"{colaborador.nome} (entrada)")
                #        solicitacao_duplicada = True

               # elif tipo_corrida == 'saida' and dados_solicitacao.get('horario_saida'):
                #    data_saida = dados_solicitacao['horario_saida'].date()
                #    saida_existente = Solicitacao.query.filter(
                #        Solicitacao.colaborador_id == colab_id,
                #        Solicitacao.tipo_corrida == 'saida',
                #        db.func.date(Solicitacao.horario_saida) == data_saida,
                #        Solicitacao.status != 'Cancelada'
                #    ).first()

                 #   if saida_existente:
                 #       solicitacoes_duplicadas.append(f"{colaborador.nome} (saída)")
                 #       solicitacao_duplicada = True

              #  elif tipo_corrida == 'desligamento' and dados_solicitacao.get('horario_desligamento'):
              #      data_desligamento = dados_solicitacao['horario_desligamento'].date()
              #      desligamento_existente = Solicitacao.query.filter(
              #          Solicitacao.colaborador_id == colab_id,
              #          Solicitacao.tipo_corrida == 'desligamento',
              #          db.func.date(Solicitacao.horario_desligamento) == data_desligamento,
              #          Solicitacao.status != 'Cancelada'
              #      ).first()
              #
              #      if desligamento_existente:
              #          solicitacoes_duplicadas.append(f"{colaborador.nome} (desligamento)")
              #          solicitacao_duplicada = True

                # Se encontrou duplicação, pula esta solicitação
              #  if solicitacao_duplicada:
              #      continue

                # Calcula valores baseado em bloco e turno
                if turno_principal_id:
                    valor, valor_repasse = buscar_valores(
                        colaborador.bloco_id, turno_principal_id)
                    if valor:
                        dados_solicitacao['valor'] = valor
                    if valor_repasse:
                        dados_solicitacao['valor_repasse'] = valor_repasse

                # Cria a solicitação
                solicitacao = Solicitacao(**dados_solicitacao)
                db.session.add(solicitacao)
                db.session.flush()  # Para obter o ID
                solicitacoes_ids_criadas.append(solicitacao.id)
                solicitacoes_criadas += 1

            db.session.commit()

            # AUDITORIA: Registra criação de solicitações
            for sol_id in solicitacoes_ids_criadas:
                log_audit(
                    action=AuditAction.CREATE,
                    resource_type='Solicitacao',
                    resource_id=sol_id,
                    status='SUCCESS',
                    severity='INFO',
                    changes={
                        'tipo_corrida': tipo_corrida,
                        'empresa_id': empresa_id,
                        'planta_id': planta_id,
                        'quantidade': solicitacoes_criadas
                    }
                )

            # Mensagens de feedback
            mensagem_sucesso = f'{solicitacoes_criadas} solicitação(ões) criada(s) com sucesso!'
            mensagem_duplicadas = ''
            
            if solicitacoes_duplicadas:
                nomes_duplicados = ', '.join(solicitacoes_duplicadas)
                mensagem_duplicadas = f'Solicitações duplicadas ignoradas para: {nomes_duplicados}'
            
            # Verifica se é requisição AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or 'application/json' in request.headers.get('Accept', ''):
                # Retorna JSON para AJAX
                return jsonify({
                    'success': True,
                    'message': mensagem_sucesso,
                    'solicitacoes_criadas': solicitacoes_criadas,
                    'solicitacoes_duplicadas': len(solicitacoes_duplicadas),
                    'mensagem_duplicadas': mensagem_duplicadas
                })
            else:
                # Retorna redirect tradicional
                if solicitacoes_criadas > 0:
                    flash(mensagem_sucesso, 'success')
                if mensagem_duplicadas:
                    flash(mensagem_duplicadas, 'warning')
                return redirect(url_for('admin.solicitacoes'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERRO] Erro ao criar solicitação: {str(e)}")
            logger.exception("Traceback completo:")
            
            mensagem_erro = f'Erro ao criar solicitações: {str(e)}'
            
            # Verifica se é requisição AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or 'application/json' in request.headers.get('Accept', ''):
                # Retorna JSON para AJAX
                return jsonify({
                    'success': False,
                    'message': mensagem_erro,
                    'solicitacoes_criadas': 0
                }), 500
            else:
                # Retorna redirect tradicional
                flash(mensagem_erro, 'danger')
                return redirect(url_for('admin.nova_solicitacao'))

    # --- LÓGICA DO GET (INTELIGENTE) ---

    # Se for admin, ele precisa da lista de empresas para escolher
    if current_user.role == 'admin':
        empresas = Empresa.query.order_by(Empresa.nome).all()
        return render_template('nova_solicitacao.html', empresas=empresas)

    # Se for supervisor, filtra apenas plantas associadas
    elif current_user.role == 'supervisor':
        if not current_user.supervisor:
            flash('Perfil de supervisor não encontrado.', 'danger')
            return redirect(url_for('home'))

        # Busca plantas associadas ao supervisor
        plantas_supervisor = current_user.supervisor.plantas  # Relacionamento many-to-many

        # Se não tiver plantas associadas, mostra aviso
        if not plantas_supervisor:
            flash(
                'Você não está associado a nenhuma planta. Entre em contato com o administrador.', 'warning')
            return redirect(url_for('home'))

        # Passa as plantas para o template
        return render_template('nova_solicitacao.html', plantas_supervisor=plantas_supervisor)

    # Se for gerente, filtra plantas dos supervisores associados
    elif current_user.role == 'gerente':
        if not current_user.gerente:
            flash('Perfil de gerente não encontrado.', 'danger')
            return redirect(url_for('home'))

        # Busca todos os supervisores do gerente
        supervisores = Supervisor.query.filter_by(
            gerente_id=current_user.gerente.id).all()

        # Busca todas as plantas dos supervisores
        plantas_gerente = []
        for supervisor in supervisores:
            plantas_gerente.extend(supervisor.plantas)

        # Remove duplicatas (caso mesma planta tenha múltiplos supervisores)
        plantas_gerente = list(set(plantas_gerente))

        # Se não tiver plantas, mostra aviso
        if not plantas_gerente:
            flash(
                'Nenhuma planta encontrada para seus supervisores. Entre em contato com o administrador.', 'warning')
            return redirect(url_for('home'))

        # Passa as plantas para o template (usando mesmo nome que supervisor)
        return render_template('nova_solicitacao.html', plantas_supervisor=plantas_gerente)


# =================================================================================================
# ROTAS: VISUALIZAR, EDITAR E EXCLUIR SOLICITAÇÕES
# =================================================================================================

@admin_bp.route('/solicitacoes/<int:id>/visualizar')
@login_required
@permission_required(['supervisor', 'admin', 'gerente'])
def visualizar_solicitacao(id):
    """Rota para visualizar uma solicitação (somente leitura)"""
    solicitacao = Solicitacao.query.get_or_404(id)

    # Verifica permissão
    if current_user.role == 'supervisor':
        if solicitacao.supervisor_id != current_user.supervisor.id:
            flash('Você não tem permissão para visualizar esta solicitação.', 'danger')
            return redirect(url_for('admin.solicitacoes'))
    elif current_user.role == 'gerente':
        # Gerente só pode ver solicitações dos seus supervisores
        ids_supervisores = [s.id for s in Supervisor.query.filter_by(
            gerente_id=current_user.gerente.id)]
        if solicitacao.supervisor_id not in ids_supervisores:
            flash('Você não tem permissão para visualizar esta solicitação.', 'danger')
            return redirect(url_for('admin.solicitacoes'))

    # Renderiza template de visualização (somente leitura)
    return render_template('visualizar_solicitacao.html', solicitacao=solicitacao)


@admin_bp.route('/solicitacoes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@permission_required(['supervisor', 'admin'])
def editar_solicitacao(id):
    solicitacao = Solicitacao.query.get_or_404(id)

    # Verifica permissão
    if current_user.role == 'supervisor':
        if solicitacao.supervisor_id != current_user.supervisor.id:
            flash('Você não tem permissão para editar esta solicitação.', 'danger')
            return redirect(url_for('admin.solicitacoes'))

    # Apenas solicitações pendentes podem ser editadas
    if solicitacao.status != 'Pendente':
        flash('Apenas solicitações pendentes podem ser editadas.', 'warning')
        return redirect(url_for('admin.solicitacoes'))

    if request.method == 'POST':
        # Captura valores antigos para auditoria
        valores_antigos = {
            'horario_entrada': solicitacao.horario_entrada.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_entrada else None,
            'horario_saida': solicitacao.horario_saida.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_saida else None,
            'horario_desligamento': solicitacao.horario_desligamento.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_desligamento else None,
            'turno_entrada_id': solicitacao.turno_entrada_id,
            'turno_saida_id': solicitacao.turno_saida_id,
            'turno_desligamento_id': solicitacao.turno_desligamento_id
        }

        try:
            # Atualiza horários baseado no tipo de corrida
            if solicitacao.tipo_corrida in ['entrada', 'entrada_saida']:
                horario_entrada_str = request.form.get('horario_entrada')
                if horario_entrada_str:
                    solicitacao.horario_entrada = datetime.strptime(
                        horario_entrada_str, '%Y-%m-%dT%H:%M')

                    # Recalcula turno de entrada
                    turno_entrada_nome = request.form.get('turno_entrada')
                    if turno_entrada_nome:
                        turno = Turno.query.filter_by(
                            nome=turno_entrada_nome, planta_id=solicitacao.planta_id).first()
                        solicitacao.turno_entrada_id = turno.id if turno else None

            if solicitacao.tipo_corrida in ['saida', 'entrada_saida']:
                horario_saida_str = request.form.get('horario_saida')
                if horario_saida_str:
                    solicitacao.horario_saida = datetime.strptime(
                        horario_saida_str, '%Y-%m-%dT%H:%M')

                    # Recalcula turno de saída
                    turno_saida_nome = request.form.get('turno_saida')
                    if turno_saida_nome:
                        turno = Turno.query.filter_by(
                            nome=turno_saida_nome, planta_id=solicitacao.planta_id).first()
                        solicitacao.turno_saida_id = turno.id if turno else None

            if solicitacao.tipo_corrida == 'desligamento':
                horario_desligamento_str = request.form.get(
                    'horario_desligamento')
                if horario_desligamento_str:
                    solicitacao.horario_desligamento = datetime.strptime(
                        horario_desligamento_str, '%Y-%m-%dT%H:%M')

                    # Recalcula turno de desligamento
                    turno_desligamento_nome = request.form.get(
                        'turno_desligamento')
                    if turno_desligamento_nome:
                        turno = Turno.query.filter_by(
                            nome=turno_desligamento_nome, planta_id=solicitacao.planta_id).first()
                        solicitacao.turno_desligamento_id = turno.id if turno else None

            # Recalcula valores
            turno_principal_id = solicitacao.turno_entrada_id or solicitacao.turno_saida_id or solicitacao.turno_desligamento_id
            if turno_principal_id and solicitacao.bloco_id:
                bloco = Bloco.query.get(solicitacao.bloco_id)
                turno = Turno.query.get(turno_principal_id)

                if bloco and turno:
                    solicitacao.valor = float(bloco.get_valor_por_turno(turno))
                    solicitacao.valor_repasse = float(
                        bloco.get_repasse_por_turno(turno))

            solicitacao.data_atualizacao = datetime.now()
            db.session.commit()

            # AUDITORIA: Registra edição de solicitação
            valores_novos = {
                'horario_entrada': solicitacao.horario_entrada.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_entrada else None,
                'horario_saida': solicitacao.horario_saida.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_saida else None,
                'horario_desligamento': solicitacao.horario_desligamento.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_desligamento else None,
                'turno_entrada_id': solicitacao.turno_entrada_id,
                'turno_saida_id': solicitacao.turno_saida_id,
                'turno_desligamento_id': solicitacao.turno_desligamento_id
            }

            mudancas = {}
            for campo, valor_novo in valores_novos.items():
                if valores_antigos[campo] != valor_novo:
                    mudancas[campo] = {
                        'before': valores_antigos[campo],
                        'after': valor_novo
                    }

            if mudancas:
                log_audit(
                    action=AuditAction.UPDATE,
                    resource_type='Solicitacao',
                    resource_id=solicitacao.id,
                    status='SUCCESS',
                    severity='INFO',
                    changes=mudancas
                )

            flash('Solicitação atualizada com sucesso!', 'success')
            return redirect(url_for('admin.solicitacoes'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar solicitação: {str(e)}', 'danger')
            import traceback
            print(traceback.format_exc())

    # GET: Renderiza formulário de edição
    return render_template('editar_solicitacao.html', solicitacao=solicitacao)


@admin_bp.route('/solicitacoes/<int:id>/excluir', methods=['POST'])
@login_required
@permission_required(['supervisor', 'admin'])
def excluir_solicitacao(id):
    solicitacao = Solicitacao.query.get_or_404(id)

    # Verifica permissão
    if current_user.role == 'supervisor':
        if solicitacao.supervisor_id != current_user.supervisor.id:
            flash('Você não tem permissão para excluir esta solicitação.', 'danger')
            return redirect(url_for('admin.solicitacoes'))

    # Apenas solicitações pendentes podem ser excluídas
    if solicitacao.status != 'Pendente':
        flash('Apenas solicitações pendentes podem ser excluídas.', 'warning')
        return redirect(url_for('admin.solicitacoes'))

    try:
        # Captura dados para auditoria ANTES de excluir
        colaborador_nome = solicitacao.colaborador.nome
        solicitacao_id = solicitacao.id
        dados_solicitacao = {
            'colaborador': colaborador_nome,
            'tipo_corrida': solicitacao.tipo_corrida,
            'horario_entrada': solicitacao.horario_entrada.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_entrada else None,
            'horario_saida': solicitacao.horario_saida.strftime('%Y-%m-%d %H:%M') if solicitacao.horario_saida else None,
            'status': solicitacao.status
        }

        db.session.delete(solicitacao)
        db.session.commit()

        # AUDITORIA: Registra exclusão
        log_audit(
            action=AuditAction.DELETE,
            resource_type='Solicitacao',
            resource_id=solicitacao_id,
            status='SUCCESS',
            severity='WARNING',  # Exclusão é WARNING
            changes={'dados_excluidos': dados_solicitacao}
        )

        flash(
            f'Solicitação de {colaborador_nome} excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir solicitação: {str(e)}', 'danger')

    return redirect(url_for('admin.solicitacoes'))


@admin_bp.route('/solicitacao/<int:solicitacao_id>/detalhes')
@login_required
@permission_required(['supervisor', 'admin'])
def detalhes_solicitacao(solicitacao_id):
    """Retorna detalhes da solicitação em formato JSON para exibição no modal"""
    try:
        solicitacao = Solicitacao.query.get_or_404(solicitacao_id)

        # Verifica permissão
        if current_user.role == 'supervisor':
            if solicitacao.supervisor_id != current_user.supervisor.id:
                return jsonify({'success': False, 'message': 'Sem permissão'}), 403

        # Monta dados da solicitação
        dados = {
            'success': True,
            'solicitacao': {
                'id': solicitacao.id,
                'tipo_corrida': solicitacao.tipo_corrida,
                'status': solicitacao.status,
                'tipo_linha': solicitacao.tipo_linha if solicitacao.tipo_linha else 'N/A',

                # Colaborador
                'colaborador_nome': solicitacao.colaborador.nome if solicitacao.colaborador else 'N/A',
                'colaborador_matricula': solicitacao.colaborador.matricula if solicitacao.colaborador else 'N/A',
                'colaborador_telefone': solicitacao.colaborador.telefone if solicitacao.colaborador else 'N/A',
                'colaborador_endereco': solicitacao.colaborador.endereco if solicitacao.colaborador else 'N/A',
                'colaborador_bairro': solicitacao.colaborador.bairro if solicitacao.colaborador and solicitacao.colaborador.bairro else 'N/A',

                # Empresa e Planta
                'empresa_nome': solicitacao.empresa.nome if solicitacao.empresa else 'N/A',
                'planta_nome': solicitacao.planta.nome if solicitacao.planta else 'N/A',

                # Bloco
                'bloco_codigo': solicitacao.bloco.codigo_bloco if solicitacao.bloco else 'N/A',

                # Centro de Custo
                'centro_custo': ', '.join([cc.nome for cc in solicitacao.colaborador.centros_custo]) if solicitacao.colaborador and solicitacao.colaborador.centros_custo else 'N/A',

                # Horários
                'horario_entrada': solicitacao.horario_entrada.strftime('%d/%m/%Y %H:%M') if solicitacao.horario_entrada else None,
                'horario_saida': solicitacao.horario_saida.strftime('%d/%m/%Y %H:%M') if solicitacao.horario_saida else None,
                'horario_desligamento': solicitacao.horario_desligamento.strftime('%d/%m/%Y %H:%M') if solicitacao.horario_desligamento else None,

                # Turnos (com tratamento seguro) - CORRIGIDO
                'turno_entrada': solicitacao.turno_entrada.nome if (solicitacao.turno_entrada and hasattr(solicitacao.turno_entrada, 'nome')) else None,
                'turno_saida': solicitacao.turno_saida.nome if (solicitacao.turno_saida and hasattr(solicitacao.turno_saida, 'nome')) else None,
                'turno_desligamento': solicitacao.turno_desligamento.nome if (solicitacao.turno_desligamento and hasattr(solicitacao.turno_desligamento, 'nome')) else None,

                # Valores
                'valor': float(solicitacao.valor) if solicitacao.valor else 0.0,
                'valor_repasse': float(solicitacao.valor_repasse) if solicitacao.valor_repasse else 0.0,

                # Viagem
                'viagem_id': solicitacao.viagem_id,

                # Supervisor
                'supervisor_nome': solicitacao.supervisor.nome if solicitacao.supervisor else 'N/A'
            }
        }

        return jsonify(dados)

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
