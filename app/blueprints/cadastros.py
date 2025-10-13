"""
Módulo de Cadastros
===================

CRUD de Empresas, Plantas, CC, Turnos, Blocos, Bairros, Gerentes, Supervisores, Motoristas.
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


@admin_bp.route('/empresas/cadastrar', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def cadastrar_empresa():
    

    if request.method == 'POST':
        nome = request.form.get('nome')
        cnpj = request.form.get('cnpj')

        # Verifica se já existe uma empresa com o mesmo nome ou CNPJ (se informado)
        if Empresa.query.filter_by(nome=nome).first():
            flash(f'A empresa "{nome}" já está cadastrada.', 'warning')
            return redirect(url_for('admin.cadastrar_empresa'))
        if cnpj and Empresa.query.filter_by(cnpj=cnpj).first():
            flash(f'O CNPJ "{cnpj}" já está em uso.', 'warning')
            return redirect(url_for('admin.cadastrar_empresa'))

        nova_empresa = Empresa(
            nome=nome,
            cnpj=cnpj,
            endereco=request.form.get('endereco'),
            telefone=request.form.get('telefone'),
            email=request.form.get('email'),
            contato=request.form.get('contato'),
            status=request.form.get('status'),
            observacoes=request.form.get('observacoes')
        )
        db.session.add(nova_empresa)
        db.session.commit()
        flash(f'Empresa "{nome}" cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='empresas'))

    # Se for GET, apenas mostra o formulário de cadastro
    return render_template('form_empresa.html', aba_ativa='empresas')


@admin_bp.route('/empresas/editar/<int:empresa_id>', methods=['GET', 'POST'])
@login_required
def editar_empresa(empresa_id):
    if current_user.role != 'admin':
        abort(403)

    empresa = Empresa.query.get_or_404(empresa_id)

    if request.method == 'POST':
        empresa.nome = request.form.get('nome')
        empresa.cnpj = request.form.get('cnpj')
        empresa.endereco = request.form.get('endereco')
        empresa.telefone = request.form.get('telefone')
        empresa.email = request.form.get('email')
        empresa.contato = request.form.get('contato')
        empresa.status = request.form.get('status')
        empresa.observacoes = request.form.get('observacoes')

        db.session.commit()
        flash(f'Empresa "{empresa.nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='empresas'))

    # Se for GET, mostra o formulário preenchido com os dados da empresa
    return render_template('form_empresa.html', aba_ativa='empresas', empresa=empresa)


@admin_bp.route('/empresas/excluir/<int:empresa_id>', methods=['POST'])
@login_required
def excluir_empresa(empresa_id):
    if current_user.role != 'admin':
        abort(403)

    empresa = Empresa.query.get_or_404(empresa_id)

    # Verificação de segurança: não permite excluir se tiver plantas associadas
    if empresa.plantas:
        flash(
            f'Não é possível excluir a empresa "{empresa.nome}", pois ela possui plantas associadas. Exclua as plantas primeiro.', 'danger')
        return redirect(url_for('admin.admin_dashboard', aba='empresas'))

    nome_empresa = empresa.nome
    db.session.delete(empresa)
    db.session.commit()
    flash(f'Empresa "{nome_empresa}" excluída com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='empresas'))


# Adicione no final de app/blueprints/admin.py

# =============================================================================
# CRUD - PLANTAS
# =============================================================================

@admin_bp.route('/plantas/cadastrar', methods=['GET', 'POST'])
@login_required
@permission_required('admin')
def cadastrar_planta():
    if request.method == 'POST':
        # --- LÓGICA DE VALIDAÇÃO DO ID ---
        planta_id = request.form.get('id')
        
        # Verifica se o ID já está em uso
        if Planta.query.get(planta_id):
            flash(f'O ID de planta "{planta_id}" já está em uso. Por favor, escolha outro.', 'danger')
            # Retorna para o formulário mantendo os dados digitados
            empresas = Empresa.query.order_by(Empresa.nome).all()
            return render_template('form_planta.html', aba_ativa='plantas', empresas=empresas)

        # --- CRIAÇÃO DA NOVA PLANTA ---
        nova_planta = Planta(
            id=planta_id,  # <-- USA O ID DO FORMULÁRIO
            nome=request.form.get('nome'),
            empresa_id=request.form.get('empresa_id')
        )
        db.session.add(nova_planta)
        db.session.commit()
        flash(f'Planta "{nova_planta.nome}" cadastrada com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='plantas'))

    # A lógica do GET permanece a mesma
    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template('form_planta.html', aba_ativa='plantas', empresas=empresas)


@admin_bp.route('/plantas/editar/<int:planta_id>', methods=['GET', 'POST'])
@login_required
def editar_planta(planta_id):
    if current_user.role != 'admin':
        abort(403)

    planta = Planta.query.get_or_404(planta_id)

    if request.method == 'POST':
        planta.nome = request.form.get('nome')
        planta.empresa_id = request.form.get('empresa_id')

        db.session.commit()
        flash(f'Planta "{planta.nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='plantas'))

    # Se for GET, busca as empresas para o dropdown e mostra o formulário preenchido
    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template('form_planta.html', aba_ativa='plantas', planta=planta, empresas=empresas)


@admin_bp.route('/plantas/excluir/<int:planta_id>', methods=['POST'])
@login_required
def excluir_planta(planta_id):
    if current_user.role != 'admin':
        abort(403)

    planta = Planta.query.get_or_404(planta_id)

    # Adicione aqui futuras verificações se necessário (ex: se a planta tem supervisores associados)
    # if planta.supervisores:
    #     flash(f'Não é possível excluir a planta "{planta.nome}" pois há supervisores associados.', 'danger')
    #     return redirect(url_for('admin.admin_dashboard', aba='plantas'))

    nome_planta = planta.nome
    db.session.delete(planta)
    db.session.commit()
    flash(f'Planta "{nome_planta}" excluída com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='plantas'))


# =============================================================================
# CRUD - CENTROS DE CUSTO
# =============================================================================

@admin_bp.route('/centros-custo/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_centro_custo():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        codigo = request.form.get('codigo')
        nome = request.form.get('nome')
        empresa_id = request.form.get('empresa_id')

        # Validação
        cc_existente = CentroCusto.query.filter_by(
            codigo=codigo, empresa_id=empresa_id).first()
        if cc_existente:
            flash(
                f'O código de centro de custo "{codigo}" já existe para esta empresa.', 'warning')
            return redirect(url_for('admin.cadastrar_centro_custo'))

        novo_cc = CentroCusto(
            codigo=codigo,
            nome=nome,
            empresa_id=empresa_id
        )
        db.session.add(novo_cc)
        db.session.commit()
        flash(f'Centro de Custo "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='centros_custo'))

    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template('form_centro_custo.html', aba_ativa='centros_custo', empresas=empresas)


@admin_bp.route('/centros-custo/editar/<int:cc_id>', methods=['GET', 'POST'])
@login_required
def editar_centro_custo(cc_id):
    if current_user.role != 'admin':
        abort(403)

    centro_custo = CentroCusto.query.get_or_404(cc_id)

    if request.method == 'POST':
        centro_custo.codigo = request.form.get('codigo')
        centro_custo.nome = request.form.get('nome')
        centro_custo.empresa_id = request.form.get('empresa_id')

        db.session.commit()
        flash(
            f'Centro de Custo "{centro_custo.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='centros_custo'))

    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template('form_centro_custo.html', aba_ativa='centros_custo', centro_custo=centro_custo, empresas=empresas)


@admin_bp.route('/centros-custo/excluir/<int:cc_id>', methods=['POST'])
@login_required
def excluir_centro_custo(cc_id):
    if current_user.role != 'admin':
        abort(403)

    centro_custo = CentroCusto.query.get_or_404(cc_id)

    # Adicionar futuras verificações aqui (ex: se está em uso por um gerente)

    nome_cc = centro_custo.nome
    db.session.delete(centro_custo)
    db.session.commit()
    flash(f'Centro de Custo "{nome_cc}" excluído com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='centros_custo'))


# Adicione no final de app/blueprints/admin.py

# =============================================================================
# CRUD - TURNOS
# =============================================================================

@admin_bp.route('/turnos/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_turno():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        nome_turno = request.form.get('nome')
        
        # Valida se o nome do turno é válido
        if not Turno.validar_nome(nome_turno):
            flash(f'Nome de turno inválido! Use um dos valores permitidos: {", ".join(Turno.TURNOS_VALIDOS)}', 'danger')
            empresas = Empresa.query.order_by(Empresa.nome).all()
            plantas = Planta.query.join(Empresa).order_by(Empresa.nome, Planta.nome).all()
            return render_template('form_turno.html', aba_ativa='turnos', empresas=empresas, plantas=plantas)
        
        novo_turno = Turno(
            nome=nome_turno,
            horario_inicio=datetime.strptime(
                request.form.get('horario_inicio'), '%H:%M').time(),
            horario_fim=datetime.strptime(
                request.form.get('horario_fim'), '%H:%M').time(),
            empresa_id=request.form.get('empresa_id'),
            planta_id=request.form.get('planta_id')
        )
        db.session.add(novo_turno)
        db.session.commit()
        flash(f'Turno "{novo_turno.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='turnos'))

    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.join(Empresa).order_by(
        Empresa.nome, Planta.nome).all()
    turnos_validos = Turno.TURNOS_VALIDOS
    return render_template('form_turno.html', aba_ativa='turnos', empresas=empresas, plantas=plantas, turnos_validos=turnos_validos)


@admin_bp.route('/turnos/editar/<int:turno_id>', methods=['GET', 'POST'])
@login_required
def editar_turno(turno_id):
    if current_user.role != 'admin':
        abort(403)

    turno = Turno.query.get_or_404(turno_id)

    if request.method == 'POST':
        nome_turno = request.form.get('nome')
        
        # Valida se o nome do turno é válido
        if not Turno.validar_nome(nome_turno):
            flash(f'Nome de turno inválido! Use um dos valores permitidos: {", ".join(Turno.TURNOS_VALIDOS)}', 'danger')
            empresas = Empresa.query.order_by(Empresa.nome).all()
            plantas = Planta.query.join(Empresa).order_by(Empresa.nome, Planta.nome).all()
            turnos_validos = Turno.TURNOS_VALIDOS
            return render_template('form_turno.html', aba_ativa='turnos', turno=turno, empresas=empresas, plantas=plantas, turnos_validos=turnos_validos)
        
        turno.nome = nome_turno
        turno.horario_inicio = datetime.strptime(
            request.form.get('horario_inicio'), '%H:%M').time()
        turno.horario_fim = datetime.strptime(
            request.form.get('horario_fim'), '%H:%M').time()
        turno.empresa_id = request.form.get('empresa_id')
        turno.planta_id = request.form.get('planta_id')

        db.session.commit()
        flash(f'Turno "{turno.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='turnos'))

    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.join(Empresa).order_by(
        Empresa.nome, Planta.nome).all()
    turnos_validos = Turno.TURNOS_VALIDOS
    return render_template('form_turno.html', aba_ativa='turnos', turno=turno, empresas=empresas, plantas=plantas, turnos_validos=turnos_validos)


@admin_bp.route('/turnos/excluir/<int:turno_id>', methods=['POST'])
@login_required
def excluir_turno(turno_id):
    if current_user.role != 'admin':
        abort(403)

    turno = Turno.query.get_or_404(turno_id)

    # Adicionar futuras verificações aqui (ex: se está em uso por um bloco)

    nome_turno = turno.nome
    db.session.delete(turno)
    db.session.commit()
    flash(f'Turno "{nome_turno}" excluído com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='turnos'))


# Adicione no final de app/blueprints/admin.py

# =============================================================================
# CRUD - BLOCOS
# =============================================================================

@admin_bp.route('/blocos/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_bloco():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        # Processa os valores dos 4 turnos fixos
        def processar_valor(campo_nome):
            valor_str = request.form.get(campo_nome, '0').replace(',', '.')
            return float(valor_str) if valor_str else 0.0
        
        novo_bloco = Bloco(
            empresa_id=request.form.get('empresa_id'),
            codigo_bloco=request.form.get('codigo_bloco'),
            nome_bloco=request.form.get('nome_bloco'),
            status=request.form.get('status'),
            # Valores dos 4 turnos fixos
            valor_turno1=processar_valor('valor_turno1'),
            repasse_turno1=processar_valor('repasse_turno1'),
            valor_turno2=processar_valor('valor_turno2'),
            repasse_turno2=processar_valor('repasse_turno2'),
            valor_turno3=processar_valor('valor_turno3'),
            repasse_turno3=processar_valor('repasse_turno3'),
            valor_admin=processar_valor('valor_admin'),
            repasse_admin=processar_valor('repasse_admin')
        )
        db.session.add(novo_bloco)
        db.session.commit()

        flash(f'Bloco "{novo_bloco.codigo_bloco}" cadastrado. Agora associe os bairros.', 'success')
        return redirect(url_for('admin.associar_bairros_bloco', bloco_id=novo_bloco.id))

    empresas = Empresa.query.filter_by(status='Ativo').order_by(Empresa.nome).all()
    turnos_validos = Turno.TURNOS_VALIDOS
    return render_template('form_bloco.html', aba_ativa='blocos', empresas=empresas, turnos_validos=turnos_validos, bloco=None)


@admin_bp.route('/blocos/editar/<int:bloco_id>', methods=['GET', 'POST'])
@login_required
def editar_bloco(bloco_id):
    if current_user.role != 'admin':
        abort(403)

    bloco = Bloco.query.get_or_404(bloco_id)

    if request.method == 'POST':
        # Processa os valores dos 4 turnos fixos
        def processar_valor(campo_nome):
            valor_str = request.form.get(campo_nome, '0').replace(',', '.')
            return float(valor_str) if valor_str else 0.0
        
        bloco.empresa_id = request.form.get('empresa_id')
        bloco.codigo_bloco = request.form.get('codigo_bloco')
        bloco.nome_bloco = request.form.get('nome_bloco')
        bloco.status = request.form.get('status')
        
        # Atualiza os valores dos 4 turnos fixos
        bloco.valor_turno1 = processar_valor('valor_turno1')
        bloco.repasse_turno1 = processar_valor('repasse_turno1')
        bloco.valor_turno2 = processar_valor('valor_turno2')
        bloco.repasse_turno2 = processar_valor('repasse_turno2')
        bloco.valor_turno3 = processar_valor('valor_turno3')
        bloco.repasse_turno3 = processar_valor('repasse_turno3')
        bloco.valor_admin = processar_valor('valor_admin')
        bloco.repasse_admin = processar_valor('repasse_admin')

        db.session.commit()
        flash(f'Bloco "{bloco.codigo_bloco}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='blocos'))

    empresas = Empresa.query.filter_by(status='Ativo').order_by(Empresa.nome).all()
    turnos_validos = Turno.TURNOS_VALIDOS
    return render_template('form_bloco.html', aba_ativa='blocos', bloco=bloco, empresas=empresas, turnos_validos=turnos_validos)


@admin_bp.route('/blocos/excluir/<int:bloco_id>', methods=['POST'])
@login_required
def excluir_bloco(bloco_id):
    if current_user.role != 'admin':
        abort(403)

    bloco = Bloco.query.get_or_404(bloco_id)

    # A exclusão em cascata configurada nos modelos cuidará de apagar
    # os valores e bairros associados automaticamente.

    nome_bloco = bloco.codigo_bloco
    db.session.delete(bloco)
    db.session.commit()
    flash(
        f'Bloco "{nome_bloco}" e todos os seus dados associados foram excluídos.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='blocos'))


# Adicione no final de admin.py

# =============================================================================
# CRUD - BAIRROS
# =============================================================================

@admin_bp.route('/bairros/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_bairro():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        nome = request.form.get('nome')
        cidade = request.form.get('cidade')

        # Validação para evitar duplicatas
        if Bairro.query.filter_by(nome=nome, cidade=cidade).first():
            flash(
                f'O bairro "{nome}" já está cadastrado na cidade "{cidade}".', 'warning')
            return redirect(request.url)

        novo_bairro = Bairro(nome=nome, cidade=cidade)
        db.session.add(novo_bairro)
        db.session.commit()
        flash('Bairro cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='bairros'))

    return render_template('form_bairro.html', aba_ativa='bairros')


@admin_bp.route('/bairros/editar/<int:bairro_id>', methods=['GET', 'POST'])
@login_required
def editar_bairro(bairro_id):
    if current_user.role != 'admin':
        abort(403)

    bairro = Bairro.query.get_or_404(bairro_id)

    if request.method == 'POST':
        bairro.nome = request.form.get('nome')
        bairro.cidade = request.form.get('cidade')
        db.session.commit()
        flash('Bairro atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='bairros'))

    return render_template('form_bairro.html', aba_ativa='bairros', bairro=bairro)


@admin_bp.route('/bairros/excluir/<int:bairro_id>', methods=['POST'])
@login_required
def excluir_bairro(bairro_id):
    if current_user.role != 'admin':
        abort(403)

    bairro = Bairro.query.get_or_404(bairro_id)

    # Verificação de segurança: não permite excluir se estiver associado a um bloco
    if bairro.bloco_id:
        flash(
            f'Não é possível excluir o bairro "{bairro.nome}", pois ele está associado ao bloco "{bairro.bloco.codigo_bloco}". Remova-o do bloco primeiro.', 'danger')
        return redirect(url_for('admin.admin_dashboard', aba='bairros'))

    nome_bairro = bairro.nome
    db.session.delete(bairro)
    db.session.commit()
    flash(f'Bairro "{nome_bairro}" excluído com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='bairros'))


@admin_bp.route('/api/get-bloco-por-bairro/<int:bairro_id>')
@login_required
def get_bloco_por_bairro(bairro_id):
    """
    Recebe o ID de um bairro e retorna o código do bloco associado em JSON.
    """
    bairro = Bairro.query.get(bairro_id)

    if bairro and bairro.bloco:
        return jsonify({'codigo_bloco': bairro.bloco.codigo_bloco})
    else:
        # Retorna 'N/A' se o bairro não for encontrado ou não tiver bloco
        return jsonify({'codigo_bloco': 'N/A'})


# =============================================================================
# NOVA ROTINA DE ASSOCIAÇÃO BLOCOS X BAIRROS
# =============================================================================

@admin_bp.route('/blocos/<int:bloco_id>/associar-bairros', methods=['GET', 'POST'])
@login_required
def associar_bairros_bloco(bloco_id):
    bloco = Bloco.query.get_or_404(bloco_id)

    if request.method == 'POST':
        # --- LÓGICA DE ASSOCIAÇÃO CORRIGIDA ---

        # 1. Pega os IDs dos bairros que o usuário quer REMOVER deste bloco
        ids_remover = request.form.getlist('bairros_a_remover')
        if ids_remover:
            # Encontra os bairros e define seu bloco_id como None (desassocia)
            Bairro.query.filter(Bairro.id.in_(ids_remover)).update(
                {'bloco_id': None}, synchronize_session=False)

        # 2. Pega os IDs dos bairros que o usuário quer ADICIONAR a este bloco
        ids_adicionar = request.form.getlist('bairros_a_adicionar')
        if ids_adicionar:
            # Encontra os bairros e define seu bloco_id para o ID do bloco atual (associa)
            Bairro.query.filter(Bairro.id.in_(ids_adicionar)).update(
                {'bloco_id': bloco.id}, synchronize_session=False)

        # 3. Salva todas as alterações no banco de dados
        db.session.commit()

        flash('Associações de bairros salvas com sucesso!', 'success')
        return redirect(url_for('admin.associar_bairros_bloco', bloco_id=bloco_id))

    # A lógica do GET para exibir a página permanece a mesma
    bairros_no_bloco = Bairro.query.filter_by(
        bloco_id=bloco.id).order_by(Bairro.nome).all()
    bairros_disponiveis = Bairro.query.filter(
        Bairro.bloco_id.is_(None)).order_by(Bairro.nome).all()

    return render_template(
        'associar_bairros.html',
        bloco=bloco,
        bairros_no_bloco=bairros_no_bloco,
        bairros_disponiveis=bairros_disponiveis
    )


# =============================================================================
# CRUD - GERENTES
# =============================================================================


@admin_bp.route('/gerentes/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_gerente():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('Este e-mail de acesso já está em uso.', 'warning')
            return redirect(request.url)

        # 1. Criar o User
        hashed_password = generate_password_hash(
            request.form.get('senha'), method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, role='gerente')
        db.session.add(new_user)
        db.session.commit()

        # 2. Criar o Gerente
        novo_gerente = Gerente(
            user_id=new_user.id,
            nome=request.form.get('nome'),
            email=email,  # Opcional, pode ser o mesmo do login
            empresa_id=request.form.get('empresa_id'),
            planta_id=request.form.get('planta_id'),
            status=request.form.get('status')
        )

        # 3. Associar Centros de Custo
        cc_ids = request.form.getlist('centros_custo')
        centros_custo = CentroCusto.query.filter(
            CentroCusto.id.in_(cc_ids)).all()
        novo_gerente.centros_custo.extend(centros_custo)

        db.session.add(novo_gerente)
        db.session.commit()
        flash(
            f'Gerente "{novo_gerente.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='gerentes'))

    # Prepara dados para o formulário GET
    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.order_by(Planta.nome).all()
    centros_custo = CentroCusto.query.order_by(CentroCusto.nome).all()
    return render_template('form_gerente.html', aba_ativa='gerentes', empresas=empresas, plantas=plantas, centros_custo=centros_custo)


@admin_bp.route('/gerentes/editar/<int:gerente_id>', methods=['GET', 'POST'])
@login_required
def editar_gerente(gerente_id):
    if current_user.role != 'admin':
        abort(403)

    gerente = Gerente.query.get_or_404(gerente_id)

    if request.method == 'POST':
        # 1. Atualizar dados do Gerente
        gerente.nome = request.form.get('nome')
        gerente.empresa_id = request.form.get('empresa_id')
        gerente.planta_id = request.form.get('planta_id')
        gerente.status = request.form.get('status')

        # 2. Atualizar dados do User
        gerente.user.email = request.form.get('email')
        nova_senha = request.form.get('senha')
        if nova_senha:
            gerente.user.password = generate_password_hash(
                nova_senha, method='pbkdf2:sha256')

        # 3. Atualizar Centros de Custo
        gerente.centros_custo.clear()  # Limpa as associações antigas
        cc_ids = request.form.getlist('centros_custo')
        centros_custo = CentroCusto.query.filter(
            CentroCusto.id.in_(cc_ids)).all()
        gerente.centros_custo.extend(centros_custo)

        db.session.commit()
        flash(f'Gerente "{gerente.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='gerentes'))

    # Prepara dados para o formulário GET
    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.order_by(Planta.nome).all()
    centros_custo = CentroCusto.query.order_by(CentroCusto.nome).all()
    return render_template('form_gerente.html', aba_ativa='gerentes', gerente=gerente, empresas=empresas, plantas=plantas, centros_custo=centros_custo)


@admin_bp.route('/gerentes/excluir/<int:gerente_id>', methods=['POST'])
@login_required
def excluir_gerente(gerente_id):
    if current_user.role != 'admin':
        abort(403)

    gerente = Gerente.query.get_or_404(gerente_id)

    # O cascade="all, delete-orphan" no modelo User cuidará de apagar o gerente
    # quando o usuário for apagado.
    user_para_excluir = gerente.user

    nome_gerente = gerente.nome
    db.session.delete(user_para_excluir)
    db.session.commit()
    flash(
        f'Gerente "{nome_gerente}" e seu usuário de acesso foram excluídos.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='gerentes'))


# =============================================================================
# CRUD - SUPERVISORES
# =============================================================================

@admin_bp.route('/supervisores/cadastrar', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente'])
def cadastrar_supervisor():
    
    if request.method == 'POST':
        if current_user.role == 'gerente':
            empresa_id = current_user.gerente.empresa_id
            gerente_id = current_user.gerente.id
        else: # Se for admin
            empresa_id = request.form.get('empresa_id')
            gerente_id = request.form.get('gerente_id')

        empresa_id = current_user.gerente.empresa_id if current_user.role == 'gerente' else request.form.get('empresa_id')
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('Este e-mail de acesso já está em uso.', 'warning')
            return redirect(request.url)

        # 1. Criar User
        hashed_password = generate_password_hash(
            request.form.get('senha'), method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password,
                        role='supervisor')
        db.session.add(new_user)
        db.session.commit()

        # 2. Criar Supervisor
        novo_supervisor = Supervisor(
            user_id=new_user.id,
            nome=request.form.get('nome'),
            matricula=request.form.get('matricula'),
            email=email,
            empresa_id=empresa_id,
            planta_id=request.form.get('planta_id'),
            gerente_id=gerente_id,
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            telefone=request.form.get('telefone')
        )

        # 3. Associar Turnos e Centros de Custo
        novo_supervisor.turnos.extend(Turno.query.filter(
            Turno.id.in_(request.form.getlist('turnos'))).all())
        novo_supervisor.centros_custo.extend(CentroCusto.query.filter(
            CentroCusto.id.in_(request.form.getlist('centros_custo'))).all())

        db.session.add(novo_supervisor)
        db.session.commit()
        flash(
            f'Supervisor "{novo_supervisor.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='supervisores'))
    
    # Prepara dados para o formulário
    if current_user.role == 'admin':
        empresas = Empresa.query.order_by(Empresa.nome).all()
        gerentes = Gerente.query.order_by(Gerente.nome).all()
    else: # Se for gerente
        empresas = [current_user.gerente.empresa]
        gerentes = [current_user.gerente] # Passa uma lista com o próprio gerente

    # Prepara dados para o formulário GET
    empresas = Empresa.query.all()
    plantas = Planta.query.all()
    gerentes = Gerente.query.all()
    turnos = Turno.query.all()
    centros_custo = CentroCusto.query.all()
    return render_template('form_supervisor.html', aba_ativa='supervisores', empresas=empresas, plantas=plantas, gerentes=gerentes, turnos=turnos, centros_custo=centros_custo)


@admin_bp.route('/supervisores/editar/<int:supervisor_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente'])
def editar_supervisor(supervisor_id):

    if current_user.role not in ['admin', 'gerente']:
        abort(403)

    supervisor = Supervisor.query.get_or_404(supervisor_id)

    if request.method == 'POST':
        # 1. Atualizar dados do Supervisor
        supervisor.nome = request.form.get('nome')
        supervisor.matricula = request.form.get('matricula')
        supervisor.empresa_id = request.form.get('empresa_id')
        supervisor.planta_id = request.form.get('planta_id')
        supervisor.gerente_id = request.form.get('gerente_id')
        supervisor.endereco = request.form.get('endereco')
        supervisor.nro = request.form.get('nro')
        supervisor.bairro = request.form.get('bairro')
        supervisor.cidade = request.form.get('cidade')
        supervisor.uf = request.form.get('uf')
        supervisor.telefone = request.form.get('telefone')

        # 2. Atualizar User
        supervisor.user.email = request.form.get('email')
        if request.form.get('senha'):
            supervisor.user.password = generate_password_hash(
                request.form.get('senha'), method='pbkdf2:sha256')

        # 3. Atualizar Turnos e Centros de Custo
        supervisor.turnos.clear()
        supervisor.centros_custo.clear()
        supervisor.turnos.extend(Turno.query.filter(
            Turno.id.in_(request.form.getlist('turnos'))).all())
        supervisor.centros_custo.extend(CentroCusto.query.filter(
            CentroCusto.id.in_(request.form.getlist('centros_custo'))).all())

        db.session.commit()
        flash(
            f'Supervisor "{supervisor.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='supervisores'))
    
    if current_user.role == 'admin':
        empresas = Empresa.query.all()
        gerentes = Gerente.query.all()
    else: # Se for gerente
        empresas = [current_user.gerente.empresa]
        gerentes = [current_user.gerente]

    # Prepara dados para o formulário GET
    empresas = Empresa.query.all()
    plantas = Planta.query.all()
    gerentes = Gerente.query.all()
    turnos = Turno.query.all()
    centros_custo = CentroCusto.query.all()
    return render_template('form_supervisor.html', aba_ativa='supervisores', supervisor=supervisor, empresas=empresas, plantas=plantas, gerentes=gerentes, turnos=turnos, centros_custo=centros_custo)


@admin_bp.route('/supervisores/excluir/<int:supervisor_id>', methods=['POST'])
@login_required
def excluir_supervisor(supervisor_id):
    if current_user.role != 'admin':
        abort(403)

    supervisor = Supervisor.query.get_or_404(supervisor_id)
    user_para_excluir = supervisor.user

    nome_supervisor = supervisor.nome
    # Apaga o User, o Supervisor é apagado em cascata
    db.session.delete(user_para_excluir)
    db.session.commit()
    flash(
        f'Supervisor "{nome_supervisor}" e seu usuário de acesso foram excluídos.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='supervisores'))


# Em app/blueprints/admin.py

# =============================================================================
# CRUD - COLABORADORES (VERSÃO FINAL E INTELIGENTE)
# =============================================================================

