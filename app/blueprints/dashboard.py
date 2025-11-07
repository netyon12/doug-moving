"""
Módulo Dashboard
================

Dashboard principal com KPIs.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from sqlalchemy import func, or_
from io import StringIO
import io
import csv
import calendar

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp


@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    # 1. Verifica se o usuário tem permissão para estar nesta área
    if current_user.role not in ['admin', 'gerente', 'supervisor']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    aba = request.args.get('aba', 'dashboard')

    # =================================================================
    # TRATAMENTO DAS ABAS COMPARTILHADAS (PRIMEIRO)
    # =================================================================

    if aba == 'supervisores':
        # Apenas Admin e Gerente podem ver supervisores
        if current_user.role not in ['admin', 'gerente']:
            abort(403)

        query = Supervisor.query.join(User)
        if current_user.role == 'gerente':
            query = query.filter(Supervisor.gerente_id ==
                                 current_user.gerente.id)

        query_filtrada = query_filters.filter_supervisores_query(
            query, request.args)
        dados = query_filtrada.order_by(Supervisor.nome).all()
        return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Supervisores', busca=request.args.get('busca', ''))

    elif aba == 'colaboradores':
        # Admin, Gerente e Supervisor podem ver colaboradores
        if current_user.role not in ['admin', 'gerente', 'supervisor']:
            abort(403)

        query = Colaborador.query
        if current_user.role == 'gerente':
            plantas_ids = [p.id for p in current_user.gerente.plantas.all()]
            if plantas_ids:
                query = query.filter(Colaborador.planta_id.in_(plantas_ids))
        elif current_user.role == 'supervisor':
            # Supervisor vê colaboradores das suas plantas
            plantas_ids = [p.id for p in current_user.supervisor.plantas]
            if plantas_ids:
                query = query.filter(Colaborador.planta_id.in_(plantas_ids))

        query_filtrada = query_filters.filter_colaboradores_query(
            query, request.args)
        dados = query_filtrada.order_by(Colaborador.nome).all()
        return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Colaboradores', busca=request.args.get('busca', ''))

    # =================================================================
    # TRATAMENTO DAS ABAS EXCLUSIVAS DO ADMIN (DEPOIS)
    # =================================================================

    elif current_user.role == 'admin':
        if aba == 'empresas':
            dados = Empresa.query.order_by(Empresa.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Empresas')

        elif aba == 'plantas':
            dados = Planta.query.join(Empresa).order_by(
                Empresa.nome, Planta.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Plantas')

        elif aba == 'centros_custo':
            dados = CentroCusto.query.join(Empresa).order_by(
                Empresa.nome, CentroCusto.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Centros de Custo')

        elif aba == 'turnos':
            dados = Turno.query.join(Empresa).join(Planta).order_by(
                Empresa.nome, Planta.nome, Turno.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Turnos')

        elif aba == 'blocos':
            base_query = Bloco.query.join(Empresa)
            query_filtrada = query_filters.filter_blocos_query(
                base_query, request.args)
            dados = query_filtrada.order_by(
                Empresa.nome, Bloco.codigo_bloco).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Blocos', busca=request.args.get('busca', ''))

        elif aba == 'bairros':
            base_query = Bairro.query
            query_filtrada = query_filters.filter_bairros_query(
                base_query, request.args)
            dados = query_filtrada.order_by(Bairro.cidade, Bairro.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Bairros', busca=request.args.get('busca', ''))

        elif aba == 'gerentes':
            base_query = Gerente.query.join(User)
            query_filtrada = query_filters.filter_gerentes_query(
                base_query, request.args)
            dados = query_filtrada.order_by(Gerente.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Gerentes', busca=request.args.get('busca', ''))

        elif aba == 'motoristas':
            base_query = Motorista.query
            query_filtrada = query_filters.filter_motoristas_query(
                base_query, request.args)
            dados = query_filtrada.order_by(Motorista.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Motoristas', busca=request.args.get('busca', ''))

        # Dashboard principal do Admin
        else:
            # ===== FILTROS =====
            # Obter filtro de empresa (padrão: primeira empresa ou ID 1)
            empresa_id = request.args.get('empresa_id', type=int)
            if not empresa_id:
                primeira_empresa = Empresa.query.order_by(Empresa.id).first()
                empresa_id = primeira_empresa.id if primeira_empresa else 1

            # Obter filtro de período (padrão: mês atual)
            hoje = datetime.now()
            primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
            ultimo_dia_mes = datetime(hoje.year, hoje.month, calendar.monthrange(
                hoje.year, hoje.month)[1], 23, 59, 59)

            data_inicio_str = request.args.get('data_inicio')
            data_fim_str = request.args.get('data_fim')

            if data_inicio_str:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            else:
                data_inicio = primeiro_dia_mes
                data_inicio_str = data_inicio.strftime('%Y-%m-%d')

            if data_fim_str:
                data_fim = datetime.strptime(
                    data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            else:
                data_fim = ultimo_dia_mes
                data_fim_str = data_fim.strftime('%Y-%m-%d')

            # Buscar todas as empresas para o dropdown
            empresas = Empresa.query.order_by(Empresa.nome).all()
            empresa_selecionada = Empresa.query.get(empresa_id)

            # ===== BUSCAR CAPACIDADE DO VEÍCULO =====
            config_capacidade = Configuracao.query.filter_by(
                chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
            capacidade_veiculo = int(
                config_capacidade.valor) if config_capacidade else 4  # Padrão: 4

            # ===== KPIs DE SOLICITAÇÕES =====
            # Otimização: Consolida COUNTs em 1 query usando GROUP BY
            counts_solicitacoes = db.session.query(
                Solicitacao.status,
                func.count(Solicitacao.id)
            ).filter(
                Solicitacao.empresa_id == empresa_id
            ).group_by(Solicitacao.status).all()

            # Converte para dicionário
            kpis_solicitacoes = {status: count for status, count in counts_solicitacoes}
            kpis_solicitacoes.setdefault('Pendente', 0)
            kpis_solicitacoes.setdefault('Agrupada', 0)
            kpis_solicitacoes.setdefault('Finalizada', 0)
            kpis_solicitacoes.setdefault('Cancelada', 0)

            # Renomeia chaves para lowercase
            kpis_solicitacoes = {
                'pendentes': kpis_solicitacoes.get('Pendente', 0),
                'agrupadas': kpis_solicitacoes.get('Agrupada', 0),
                'finalizadas': kpis_solicitacoes.get('Finalizada', 0),
                'canceladas': kpis_solicitacoes.get('Cancelada', 0)
            }

            # Finalizadas e Canceladas do período (queries separadas necessárias)
            kpis_solicitacoes['finalizadas_periodo'] = Solicitacao.query.filter(
                Solicitacao.empresa_id == empresa_id,
                Solicitacao.status == 'Finalizada',
                Solicitacao.data_atualizacao >= data_inicio,
                Solicitacao.data_atualizacao <= data_fim
            ).count()
            kpis_solicitacoes['canceladas_periodo'] = Solicitacao.query.filter(
                Solicitacao.empresa_id == empresa_id,
                Solicitacao.status == 'Cancelada',
                Solicitacao.data_atualizacao >= data_inicio,
                Solicitacao.data_atualizacao <= data_fim
            ).count()

            # ===== KPIs DE VIAGENS =====
            # Otimização: Consolida COUNTs em 1 query usando GROUP BY
            counts_viagens = db.session.query(
                Viagem.status,
                func.count(Viagem.id)
            ).filter(
                Viagem.empresa_id == empresa_id
            ).group_by(Viagem.status).all()

            # Converte para dicionário
            kpis_viagens = {status: count for status, count in counts_viagens}
            kpis_viagens.setdefault('Pendente', 0)
            kpis_viagens.setdefault('Agendada', 0)
            kpis_viagens.setdefault('Em Andamento', 0)
            kpis_viagens.setdefault('Finalizada', 0)
            kpis_viagens.setdefault('Cancelada', 0)

            # Renomeia chaves para lowercase
            kpis_viagens = {
                'pendentes': kpis_viagens.get('Pendente', 0),
                'agendadas': kpis_viagens.get('Agendada', 0),
                'em_andamento': kpis_viagens.get('Em Andamento', 0),
                'finalizadas_total': kpis_viagens.get('Finalizada', 0),
                'canceladas_total': kpis_viagens.get('Cancelada', 0)
            }

            # Viagens finalizadas e canceladas DO PERÍODO (queries separadas necessárias)
            kpis_viagens['finalizadas_periodo'] = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Finalizada',
                Viagem.data_finalizacao >= data_inicio,
                Viagem.data_finalizacao <= data_fim
            ).count()

            kpis_viagens['canceladas_periodo'] = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Cancelada',
                Viagem.data_criacao >= data_inicio,
                Viagem.data_criacao <= data_fim
            ).count()

            # ===== KPIs DE MOTORISTAS (SEM FILTRO DE DATA) =====
            # Busca TODOS os motoristas ativos (independente de terem viagens)
            motoristas_empresa = Motorista.query.filter_by(
                status='Ativo').all()

            kpis_motoristas = {
                'disponiveis': 0,
                'agendados': 0,
                'ocupados': 0,
                'offline': 0
            }

            for motorista in motoristas_empresa:
                status_atual = motorista.get_status_atual()

                # Disponíveis = disponivel + agendado (conforme regra de negócio)
                if status_atual in ['disponivel', 'agendado']:
                    kpis_motoristas['disponiveis'] += 1

                # Contadores específicos
                if status_atual == 'agendado':
                    kpis_motoristas['agendados'] += 1
                elif status_atual == 'ocupado':
                    kpis_motoristas['ocupados'] += 1
                elif status_atual == 'offline':
                    kpis_motoristas['offline'] += 1

            # ===== MÉTRICAS DE PERFORMANCE (COM FILTRO DE PERÍODO) =====

            # Buscar viagens finalizadas no período
            viagens_finalizadas_periodo = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Finalizada',
                Viagem.data_finalizacao >= data_inicio,
                Viagem.data_finalizacao <= data_fim
            ).all()

            # Receita total
            receita_total = sum(
                [v.valor for v in viagens_finalizadas_periodo if v.valor]) or 0

            # Custo de repasse
            custo_repasse = sum(
                [v.valor_repasse for v in viagens_finalizadas_periodo if v.valor_repasse]) or 0

            # Margem líquida
            margem_liquida = receita_total - custo_repasse

            # Total de passageiros (conta solicitações associadas às viagens)
            total_passageiros = 0
            for viagem in viagens_finalizadas_periodo:
                passageiros_viagem = Solicitacao.query.filter_by(
                    viagem_id=viagem.id).count()
                total_passageiros += passageiros_viagem

            # Taxa de ocupação CORRIGIDA
            num_viagens_finalizadas = len(viagens_finalizadas_periodo)
            if num_viagens_finalizadas > 0:
                taxa_ocupacao = (
                    total_passageiros / (num_viagens_finalizadas * capacidade_veiculo)) * 100
            else:
                taxa_ocupacao = 0

            # Ticket médio
            ticket_medio = (
                receita_total / num_viagens_finalizadas) if num_viagens_finalizadas > 0 else 0

            # Tempo médio de viagem (em minutos)
            viagens_com_tempo = [
                v for v in viagens_finalizadas_periodo if v.data_inicio and v.data_finalizacao]

            if viagens_com_tempo:
                tempos = []
                for viagem in viagens_com_tempo:
                    duracao = (viagem.data_finalizacao -
                               viagem.data_inicio).total_seconds() / 60
                    tempos.append(duracao)
                tempo_medio = sum(tempos) / len(tempos)
            else:
                tempo_medio = 0

            # Viagens por motorista
            motoristas_ativos = db.session.query(Viagem.motorista_id).filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Finalizada',
                Viagem.data_finalizacao >= data_inicio,
                Viagem.data_finalizacao <= data_fim,
                Viagem.motorista_id.isnot(None)
            ).distinct().count()

            viagens_por_motorista = (
                num_viagens_finalizadas / motoristas_ativos) if motoristas_ativos > 0 else 0

            # Taxa de cancelamento
            viagens_canceladas_periodo = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Cancelada',
                Viagem.data_criacao >= data_inicio,
                Viagem.data_criacao <= data_fim
            ).count()

            total_viagens_periodo = num_viagens_finalizadas + viagens_canceladas_periodo
            taxa_cancelamento = (viagens_canceladas_periodo /
                                 total_viagens_periodo * 100) if total_viagens_periodo > 0 else 0

            # ===== COMPARAÇÃO COM PERÍODO ANTERIOR =====
            dias_periodo = (data_fim - data_inicio).days + 1
            data_inicio_anterior = data_inicio - timedelta(days=dias_periodo)
            data_fim_anterior = data_inicio - timedelta(days=1)

            viagens_anterior = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Finalizada',
                Viagem.data_finalizacao >= data_inicio_anterior,
                Viagem.data_finalizacao <= data_fim_anterior
            ).all()

            receita_anterior = sum(
                [v.valor for v in viagens_anterior if v.valor]) or 0
            margem_anterior = sum(
                [(v.valor or 0) - (v.valor_repasse or 0) for v in viagens_anterior]) or 0
            num_viagens_anterior = len(viagens_anterior)

            # Calcular variações percentuais
            variacao_receita = ((receita_total - receita_anterior) /
                                receita_anterior * 100) if receita_anterior > 0 else 0
            variacao_margem = ((margem_liquida - margem_anterior) /
                               margem_anterior * 100) if margem_anterior > 0 else 0
            variacao_viagens = ((num_viagens_finalizadas - num_viagens_anterior) /
                                num_viagens_anterior * 100) if num_viagens_anterior > 0 else 0

            kpis_performance = {
                'receita_total': float(receita_total),
                'custo_repasse': float(custo_repasse),
                'margem_liquida': float(margem_liquida),
                'taxa_ocupacao': round(taxa_ocupacao, 1),
                'ticket_medio': round(ticket_medio, 2),
                'tempo_medio_viagem': round(tempo_medio, 1),
                'viagens_por_motorista': round(viagens_por_motorista, 1),
                'taxa_cancelamento': round(taxa_cancelamento, 1),
                'total_passageiros': total_passageiros,
                'capacidade_veiculo': capacidade_veiculo,
                'num_viagens_finalizadas': num_viagens_finalizadas,
                # Comparações
                'variacao_receita': round(variacao_receita, 1),
                'variacao_margem': round(variacao_margem, 1),
                'variacao_viagens': round(variacao_viagens, 1)
            }

            # ===== DADOS GERAIS =====
            kpis_gerais = {
                'total_empresas': Empresa.query.count(),
                'total_plantas': Planta.query.filter_by(empresa_id=empresa_id).count(),
                'total_motoristas': len(motoristas_empresa),
                'total_colaboradores': Colaborador.query.join(Planta).filter(Planta.empresa_id == empresa_id).count()
            }

            # ===== DADOS PARA GRÁFICOS =====
            # Gráfico 1: Receita Diária do Período
            receita_diaria = []
            labels_dias = []
            data_atual = data_inicio
            while data_atual <= data_fim:
                data_fim_dia = data_atual.replace(
                    hour=23, minute=59, second=59)
                receita_dia = db.session.query(func.sum(Viagem.valor)).filter(
                    Viagem.empresa_id == empresa_id,
                    Viagem.status == 'Finalizada',
                    Viagem.data_finalizacao >= data_atual,
                    Viagem.data_finalizacao <= data_fim_dia
                ).scalar() or 0

                receita_diaria.append(float(receita_dia))
                labels_dias.append(data_atual.strftime('%d/%m'))
                data_atual += timedelta(days=1)

            # Gráfico 2: Distribuição de Viagens por Status (usar KPIs já calculados)
            dados_graficos = {
                'receita_diaria': receita_diaria,
                'labels_dias': labels_dias,
                'viagens_por_status': {
                    'labels': ['Pendentes', 'Agendadas', 'Em Andamento', 'Finalizadas', 'Canceladas'],
                    'valores': [
                        kpis_viagens['pendentes'],
                        kpis_viagens['agendadas'],
                        kpis_viagens['em_andamento'],
                        kpis_viagens['finalizadas_periodo'],
                        kpis_viagens['canceladas_periodo']
                    ]
                }
            }

            return render_template(
                'admin/admin_dashboard_main.html',
                aba_ativa='dashboard',
                empresas=empresas,
                empresa_selecionada=empresa_selecionada,
                kpis_solicitacoes=kpis_solicitacoes,
                kpis_viagens=kpis_viagens,
                kpis_motoristas=kpis_motoristas,
                kpis_performance=kpis_performance,
                kpis_gerais=kpis_gerais,
                dados_graficos=dados_graficos,
                data_inicio=data_inicio_str,
                data_fim=data_fim_str
            )

    # Se um usuário não-admin tentar acessar uma aba não autorizada, redireciona para o dashboard principal dele
    return redirect(url_for('home'))
