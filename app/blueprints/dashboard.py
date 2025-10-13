"""
Módulo Dashboard
================

Dashboard principal com KPIs.
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
            query = query.filter(Supervisor.gerente_id == current_user.gerente.id)
        
        query_filtrada = query_filters.filter_supervisores_query(query, request.args)
        dados = query_filtrada.order_by(Supervisor.nome).all()
        return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Supervisores', busca=request.args.get('busca', ''))

    elif aba == 'colaboradores':
        # Admin, Gerente e Supervisor podem ver colaboradores
        if current_user.role not in ['admin', 'gerente', 'supervisor']:
            abort(403)

        query = Colaborador.query
        if current_user.role == 'gerente':
            query = query.filter(Colaborador.planta_id == current_user.gerente.planta_id)
        elif current_user.role == 'supervisor':
            # Supervisor vê colaboradores da sua própria planta
            query = query.filter(Colaborador.planta_id == current_user.supervisor.planta_id)

        query_filtrada = query_filters.filter_colaboradores_query(query, request.args)
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
            dados = Planta.query.join(Empresa).order_by(Empresa.nome, Planta.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Plantas')
        
        elif aba == 'centros_custo':
            dados = CentroCusto.query.join(Empresa).order_by(Empresa.nome, CentroCusto.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Centros de Custo')

        elif aba == 'turnos':
            dados = Turno.query.join(Empresa).join(Planta).order_by(Empresa.nome, Planta.nome, Turno.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Turnos')

        elif aba == 'blocos':
            base_query = Bloco.query.join(Empresa)
            query_filtrada = query_filters.filter_blocos_query(base_query, request.args)
            dados = query_filtrada.order_by(Empresa.nome, Bloco.codigo_bloco).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Blocos', busca=request.args.get('busca', ''))
        
        elif aba == 'bairros':
            base_query = Bairro.query
            query_filtrada = query_filters.filter_bairros_query(base_query, request.args)
            dados = query_filtrada.order_by(Bairro.cidade, Bairro.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Bairros', busca=request.args.get('busca', ''))
        
        elif aba == 'gerentes':
            base_query = Gerente.query.join(User)
            query_filtrada = query_filters.filter_gerentes_query(base_query, request.args)
            dados = query_filtrada.order_by(Gerente.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Gerentes', busca=request.args.get('busca', ''))

        elif aba == 'motoristas':
            base_query = Motorista.query
            query_filtrada = query_filters.filter_motoristas_query(base_query, request.args)
            dados = query_filtrada.order_by(Motorista.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Motoristas', busca=request.args.get('busca', ''))
        
        # Dashboard principal do Admin
        else:
            # Obter filtro de empresa (padrão: primeira empresa ou ID 1)
            empresa_id = request.args.get('empresa_id', type=int)
            if not empresa_id:
                primeira_empresa = Empresa.query.order_by(Empresa.id).first()
                empresa_id = primeira_empresa.id if primeira_empresa else 1
            
            # Buscar todas as empresas para o dropdown
            empresas = Empresa.query.order_by(Empresa.nome).all()
            empresa_selecionada = Empresa.query.get(empresa_id)
            
            # ===== KPIs DE SOLICITAÇÕES =====
            kpis_solicitacoes = {
                'pendentes': Solicitacao.query.filter_by(empresa_id=empresa_id, status='Pendente').count(),
                'agrupadas': Solicitacao.query.filter_by(empresa_id=empresa_id, status='Agrupada').count(),
                'finalizadas': Solicitacao.query.filter_by(empresa_id=empresa_id, status='Finalizada').count(),
                'canceladas': Solicitacao.query.filter_by(empresa_id=empresa_id, status='Cancelada').count()
            }
            
            # ===== KPIs DE VIAGENS =====
            kpis_viagens = {
                'pendentes': Viagem.query.filter_by(empresa_id=empresa_id, status='Pendente').count(),
                'agendadas': Viagem.query.filter_by(empresa_id=empresa_id, status='Agendada').count(),
                'em_andamento': Viagem.query.filter_by(empresa_id=empresa_id, status='Em Andamento').count(),
                'finalizadas': Viagem.query.filter_by(empresa_id=empresa_id, status='Finalizada').count(),
                'canceladas': Viagem.query.filter_by(empresa_id=empresa_id, status='Cancelada').count()
            }
            
            # ===== KPIs DE MOTORISTAS =====
            # Obter todos os motoristas (não há empresa_id direto no modelo Motorista)
            # Vamos buscar motoristas que têm viagens relacionadas à empresa
            motoristas_ids_com_viagens = db.session.query(Viagem.motorista_id).filter(
                Viagem.empresa_id == empresa_id,
                Viagem.motorista_id.isnot(None)
            ).distinct().all()
            
            motoristas_ids = [m[0] for m in motoristas_ids_com_viagens]
            
            # Se não houver motoristas com viagens, busca todos os motoristas
            if motoristas_ids:
                motoristas_empresa = Motorista.query.filter(Motorista.id.in_(motoristas_ids)).all()
            else:
                motoristas_empresa = Motorista.query.all()
            
            kpis_motoristas = {
                'disponiveis': 0,
                'agendados': 0,
                'ocupados': 0,
                'offline': 0
            }
            
            for motorista in motoristas_empresa:
                status_atual = motorista.get_status_atual()
                if status_atual == 'disponivel':
                    kpis_motoristas['disponiveis'] += 1
                elif status_atual == 'agendado':
                    kpis_motoristas['agendados'] += 1
                elif status_atual == 'ocupado':
                    kpis_motoristas['ocupados'] += 1
                else:
                    kpis_motoristas['offline'] += 1
            
            # ===== KPIs ADICIONAIS =====
            # Receita total (soma de valores de viagens finalizadas)
            receita_total = db.session.query(func.sum(Viagem.valor)).filter_by(
                empresa_id=empresa_id,
                status='Finalizada'
            ).scalar() or 0
            
            # Taxa de ocupação (viagens finalizadas / total de viagens)
            total_viagens = Viagem.query.filter_by(empresa_id=empresa_id).count()
            viagens_finalizadas = kpis_viagens['finalizadas']
            taxa_ocupacao = (viagens_finalizadas / total_viagens * 100) if total_viagens > 0 else 0
            
            # Tempo médio de viagem (em minutos)
            viagens_com_tempo = Viagem.query.filter(
                Viagem.empresa_id == empresa_id,
                Viagem.status == 'Finalizada',
                Viagem.data_inicio.isnot(None),
                Viagem.data_finalizacao.isnot(None)
            ).all()
            
            if viagens_com_tempo:
                tempos = []
                for viagem in viagens_com_tempo:
                    duracao = (viagem.data_finalizacao - viagem.data_inicio).total_seconds() / 60
                    tempos.append(duracao)
                tempo_medio = sum(tempos) / len(tempos)
            else:
                tempo_medio = 0
            
            kpis_adicionais = {
                'receita_total': float(receita_total),
                'taxa_ocupacao': round(taxa_ocupacao, 1),
                'tempo_medio_viagem': round(tempo_medio, 1)
            }
            
            # ===== DADOS GERAIS =====
            kpis_gerais = {
                'total_empresas': Empresa.query.count(),
                'total_plantas': Planta.query.filter_by(empresa_id=empresa_id).count(),
                'total_motoristas': len(motoristas_empresa),
                'total_colaboradores': Colaborador.query.join(Planta).filter(Planta.empresa_id == empresa_id).count()
            }
            
            return render_template(
                'admin/admin_dashboard_main.html',
                aba_ativa='dashboard',
                empresas=empresas,
                empresa_selecionada=empresa_selecionada,
                kpis_solicitacoes=kpis_solicitacoes,
                kpis_viagens=kpis_viagens,
                kpis_motoristas=kpis_motoristas,
                kpis_adicionais=kpis_adicionais,
                kpis_gerais=kpis_gerais
            )
    
    # Se um usuário não-admin tentar acessar uma aba não autorizada, redireciona para o dashboard principal dele
    return redirect(url_for('home'))




# =============================================================================
# CRUD - EMPRESAS
# =============================================================================

