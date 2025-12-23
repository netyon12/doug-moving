"""
Dashboard - Rota Principal
==========================

Rota principal /admin/dashboard com:
- Tratamento de abas de cadastros (empresas, plantas, etc.)
- Chamada dos módulos de KPIs (operacional, executivo, gráficos)
- Controle de permissões por perfil

Permissões: Admin e Operador (com restrições por KPI)
"""

from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db, query_filters
from app.models import (
    Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista
)

from ..admin import admin_bp

# Importa módulos do dashboard
from .dash_utils import get_filtros, get_permissoes_usuario
from .dash_operacional import get_todos_kpis_operacionais
from .dash_executivo import get_todos_kpis_executivos
from .dash_graficos import get_todos_graficos


@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    """
    Rota principal do dashboard administrativo.
    Trata abas de cadastros e exibe KPIs do dashboard principal.
    """
    
    # 1. Verifica se o usuário tem permissão para estar nesta área
    if current_user.role not in ['admin', 'gerente', 'supervisor', 'operador']:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    aba = request.args.get('aba', 'dashboard')

    # =================================================================
    # TRATAMENTO DAS ABAS COMPARTILHADAS (PRIMEIRO)
    # =================================================================

    if aba == 'supervisores':
        # Apenas Admin e Gerente podem ver supervisores
        if current_user.role not in ['admin', 'gerente', 'operador']:
            abort(403)

        from app.models import User
        query = Supervisor.query.join(User)
        if current_user.role == 'gerente':
            query = query.filter(Supervisor.gerente_id == current_user.gerente.id)

        query_filtrada = query_filters.filter_supervisores_query(query, request.args)
        dados = query_filtrada.order_by(Supervisor.nome).all()
        return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Supervisores', busca=request.args.get('busca', ''))

    elif aba == 'colaboradores':
        # Admin, Gerente, Supervisor e Operador podem ver colaboradores
        if current_user.role not in ['admin', 'gerente', 'supervisor', 'operador']:
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

        query_filtrada = query_filters.filter_colaboradores_query(query, request.args)
        dados = query_filtrada.order_by(Colaborador.nome).all()
        return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Colaboradores', busca=request.args.get('busca', ''))

    # =================================================================
    # TRATAMENTO DAS ABAS EXCLUSIVAS DO ADMIN E OPERADOR
    # =================================================================

    elif current_user.role in ['admin', 'operador']:
        
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
            from app.models import User
            base_query = Gerente.query.join(User)
            query_filtrada = query_filters.filter_gerentes_query(base_query, request.args)
            dados = query_filtrada.order_by(Gerente.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Gerentes', busca=request.args.get('busca', ''))

        elif aba == 'motoristas':
            base_query = Motorista.query
            query_filtrada = query_filters.filter_motoristas_query(base_query, request.args)
            dados = query_filtrada.order_by(Motorista.nome).all()
            return render_template('admin/admin_cadastros.html', aba_ativa=aba, dados=dados, titulo='Motoristas', busca=request.args.get('busca', ''))

        # =================================================================
        # DASHBOARD PRINCIPAL (KPIs)
        # =================================================================
        else:
            # Obtém filtros de empresa e período
            filtros = get_filtros()
            empresa_id = filtros['empresa_id']
            data_inicio = filtros['data_inicio']
            data_fim = filtros['data_fim']
            
            # ===== KPIs OPERACIONAIS =====
            kpis_operacionais = get_todos_kpis_operacionais(empresa_id, data_inicio, data_fim)
            
            # ===== KPIs EXECUTIVOS =====
            kpis_executivos = get_todos_kpis_executivos(empresa_id, data_inicio, data_fim)
            
            # ===== GRÁFICOS =====
            # Passa kpis_viagens para evitar query duplicada
            kpis_viagens = kpis_operacionais.get('viagens') if kpis_operacionais else None
            dados_graficos = get_todos_graficos(empresa_id, data_inicio, data_fim, kpis_viagens)
            
            # ===== PERMISSÕES DO USUÁRIO =====
            permissoes = get_permissoes_usuario()

            # Monta dicionários no formato esperado pelo template
            # (mantém compatibilidade com template existente)
            kpis_solicitacoes = kpis_operacionais.get('solicitacoes') if kpis_operacionais else {}
            kpis_viagens = kpis_operacionais.get('viagens') if kpis_operacionais else {}
            kpis_motoristas = kpis_operacionais.get('motoristas') if kpis_operacionais else {}
            kpis_gerais = kpis_operacionais.get('gerais') if kpis_operacionais else {}
            
            # KPIs de performance (executivo) - monta no formato esperado
            kpis_performance = kpis_executivos if kpis_executivos else {}

            return render_template(
                'admin/admin_dashboard_main.html',
                aba_ativa='dashboard',
                empresas=filtros['empresas'],
                empresa_selecionada=filtros['empresa_selecionada'],
                kpis_solicitacoes=kpis_solicitacoes,
                kpis_viagens=kpis_viagens,
                kpis_motoristas=kpis_motoristas,
                kpis_performance=kpis_performance,
                kpis_gerais=kpis_gerais,
                dados_graficos=dados_graficos,
                data_inicio=filtros['data_inicio_str'],
                data_fim=filtros['data_fim_str'],
                permissoes=permissoes  # Novo: passa permissões para o template
            )

    # Se um usuário não autorizado tentar acessar, redireciona para o dashboard dele
    return redirect(url_for('home'))
