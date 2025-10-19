"""
Módulo de Colaboradores
=======================

CRUD e importação de colaboradores.
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


@admin_bp.route('/colaboradores/cadastrar', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente', 'supervisor'])
def cadastrar_colaborador():
    
    if request.method == 'POST':

        # Lógica para pegar o ID da empresa e planta corretamente
        if current_user.role == 'supervisor':
            empresa_id = current_user.supervisor.empresa_id
            planta_id = request.form.get('planta_id')
            if not planta_id and current_user.supervisor.plantas:
                planta_id = current_user.supervisor.plantas[0].id
        else: # Para Admin e Gerente
            empresa_id = request.form.get('empresa_id')
            planta_id = request.form.get('planta_id')

        # Validação do telefone
        telefone = request.form.get('telefone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if telefone and (not telefone.isdigit() or len(telefone) != 11):
            flash('O telefone deve conter exatamente 11 dígitos (DDD + número). Exemplo: 81988751618', 'warning')
            # Retorna para o formulário mantendo os dados
            if current_user.role == 'admin':
                empresas = Empresa.query.all()
                plantas = Planta.query.all()
            elif current_user.role == 'gerente':
                empresas = [current_user.gerente.empresa]
                plantas = Planta.query.filter_by(empresa_id=current_user.gerente.empresa_id).all()
            else:
                empresas = [current_user.supervisor.empresa]
                plantas = current_user.supervisor.plantas
            blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
            return render_template('form_colaborador.html', aba_ativa='colaboradores', empresas=empresas, plantas=plantas, blocos=blocos)

        novo_colaborador = Colaborador(
            nome=request.form.get('nome'),
            matricula=request.form.get('matricula'),
            empresa_id=empresa_id,
            planta_id=planta_id,
            status=request.form.get('status'),
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            telefone=telefone,
            email=request.form.get('email'),
            bloco_id=request.form.get('bloco_id') or None
        )
        db.session.add(novo_colaborador)
        db.session.commit()
        flash(f'Colaborador "{novo_colaborador.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

    # Lógica do GET: passa todos os dados para os dropdowns
    if current_user.role == 'admin':
        empresas = Empresa.query.all()
        plantas = Planta.query.all()
    elif current_user.role == 'gerente':
        empresas = [current_user.gerente.empresa]
        plantas = Planta.query.filter_by(empresa_id=current_user.gerente.empresa_id).all()
    else: # Supervisor
        empresas = [current_user.supervisor.empresa]
        plantas = current_user.supervisor.plantas  # Múltiplas plantas

    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()

    return render_template(
        'form_colaborador.html',
        aba_ativa='colaboradores',
        empresas=empresas,
        plantas=plantas,
        blocos=blocos  # Adiciona blocos ao contexto
    )


@admin_bp.route('/colaboradores/editar/<int:colaborador_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente', 'supervisor'])
def editar_colaborador(colaborador_id):
    colaborador = Colaborador.query.get_or_404(colaborador_id)
    
    if current_user.role not in ['admin', 'supervisor', 'gerente']:
        abort(403)
    
    if request.method == 'POST':

        if current_user.role == 'supervisor':
            colaborador.empresa_id = current_user.supervisor.empresa_id
            planta_id = request.form.get('planta_id')
            if not planta_id and current_user.supervisor.plantas:
                planta_id = current_user.supervisor.plantas[0].id
            colaborador.planta_id = planta_id
        else:
            colaborador.empresa_id = request.form.get('empresa_id')
            colaborador.planta_id = request.form.get('planta_id')

        # Validação do telefone
        telefone = request.form.get('telefone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        if telefone and (not telefone.isdigit() or len(telefone) != 11):
            flash('O telefone deve conter exatamente 11 dígitos (DDD + número). Exemplo: 81988751618', 'warning')
            if current_user.role == 'admin':
                empresas = Empresa.query.all()
                plantas = Planta.query.all()
            else:
                empresas = [current_user.empresa]
                plantas = [current_user.planta]
            blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
            return render_template('form_colaborador.html', aba_ativa='colaboradores', colaborador=colaborador, empresas=empresas, plantas=plantas, blocos=blocos)

        colaborador.nome = request.form.get('nome')
        colaborador.matricula = request.form.get('matricula')
        colaborador.status = request.form.get('status')
        colaborador.endereco = request.form.get('endereco')
        colaborador.nro = request.form.get('nro')
        colaborador.bairro = request.form.get('bairro')
        colaborador.cidade = request.form.get('cidade')
        colaborador.uf = request.form.get('uf')
        colaborador.telefone = telefone
        colaborador.email = request.form.get('email')
        colaborador.bloco_id = request.form.get('bloco_id') or None

        db.session.commit()
        flash(f'Colaborador "{colaborador.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

    # Lógica do GET para edição
    if current_user.role == 'admin':
            empresas = Empresa.query.all()
            plantas = Planta.query.all()
    else: # Gerente ou Supervisor
            empresas = [current_user.empresa]
            plantas = [current_user.planta]

    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()

    return render_template(
        'form_colaborador.html',
        aba_ativa='colaboradores',
        colaborador=colaborador,
        empresas=empresas,
        plantas=plantas,
        blocos=blocos
    )


@admin_bp.route('/colaboradores/excluir/<int:colaborador_id>', methods=['POST'])
@login_required
def excluir_colaborador(colaborador_id):
    # Apenas o admin pode excluir
    if current_user.role != 'admin':
        abort(403)

    colaborador = Colaborador.query.get_or_404(colaborador_id)

    # Verificação de segurança (opcional, mas recomendada): impede a exclusão se tiver solicitações associadas
    # if Solicitacao.query.filter_by(colaborador_id=colaborador.id).first():
    #     flash(f'Não é possível excluir o colaborador "{colaborador.nome}", pois ele possui solicitações de transporte associadas.', 'danger')
    #     return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

    nome_colaborador = colaborador.nome
    db.session.delete(colaborador)
    db.session.commit()

    flash(f'Colaborador "{nome_colaborador}" excluído com sucesso.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

# =============================================================================
# ROTA DE API PARA BUSCAR BLOCO (VERSÃO MELHORADA)
# =============================================================================


@admin_bp.route('/api/buscar-bloco-por-bairro')
@login_required
def buscar_bloco_por_bairro():
    import unicodedata
    
    nome_bairro_input = request.args.get('bairro', '', type=str).strip()
    if not nome_bairro_input:
        return jsonify({'error': 'Nome do bairro não fornecido'}), 400

    def normalizar_texto(texto):
        """
        Normaliza o texto removendo acentos, pontos e convertendo para minúsculas.
        Exemplo: 'JD. ITAPUÃ' -> 'jd itapua'
        """
        # Remove acentos (NFD = Normalization Form Decomposed)
        texto_sem_acento = unicodedata.normalize('NFD', texto)
        texto_sem_acento = ''.join(c for c in texto_sem_acento if unicodedata.category(c) != 'Mn')
        # Remove pontos e espaços duplos, converte para minúsculas
        texto_limpo = texto_sem_acento.lower().replace('.', '').replace('  ', ' ').strip()
        return texto_limpo

    # 1. Normaliza a entrada do usuário
    termo_busca_limpo = normalizar_texto(nome_bairro_input)

    # 2. Busca todos os bairros e compara manualmente (já que SQLite não tem função de remover acentos)
    todos_bairros = Bairro.query.all()
    
    for bairro_obj in todos_bairros:
        nome_banco_normalizado = normalizar_texto(bairro_obj.nome)
        if nome_banco_normalizado == termo_busca_limpo:
            if bairro_obj.bloco:
                return jsonify({
                    'bloco_id': bairro_obj.bloco.id,
                    'bloco_codigo': bairro_obj.bloco.codigo_bloco
                })
            else:
                # Bairro encontrado mas sem bloco associado
                return jsonify({'bloco_codigo': 'Bloco não encontrado'}), 404
    
    # Bairro não encontrado
    return jsonify({'bloco_codigo': 'Bloco não encontrado'}), 404


# Em app/blueprints/admin.py

# =============================================================================
# CRUD - MOTORISTAS
# =============================================================================

@admin_bp.route('/motoristas/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar_motorista():
    if current_user.role != 'admin':
        abort(403)

    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('Este e-mail de acesso já está em uso.', 'warning')
            return redirect(request.url)

        hashed_password = generate_password_hash(
            request.form.get('senha'), method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password,
                        role='motorista')
        db.session.add(new_user)
        db.session.commit()

        novo_motorista = Motorista(
            user_id=new_user.id,
            nome=request.form.get('nome'),
            cpf_cnpj=request.form.get('cpf_cnpj'),
            endereco=request.form.get('endereco'),
            nro=request.form.get('nro'),
            bairro=request.form.get('bairro'),
            cidade=request.form.get('cidade'),
            uf=request.form.get('uf'),
            telefone=request.form.get('telefone'),
            email=email,
            chave_pix=request.form.get('pix'),
            status=request.form.get('status'),

            # --- CAMPOS DO VEÍCULO CORRIGIDOS ---
            veiculo_nome=request.form.get('veiculo'),
            veiculo_placa=request.form.get('placa'),
            veiculo_cor=request.form.get('cor'),
            veiculo_ano=request.form.get('ano') or None,
            veiculo_km=request.form.get('km_veiculo') or None,
            veiculo_obs=request.form.get('observacoes')
        )
        db.session.add(novo_motorista)
        db.session.commit()
        flash(
            f'Motorista "{novo_motorista.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='motoristas'))

    return render_template('form_motorista.html', aba_ativa='motoristas')


@admin_bp.route('/motoristas/editar/<int:motorista_id>', methods=['GET', 'POST'])
@login_required
def editar_motorista(motorista_id):
    if current_user.role != 'admin':
        abort(403)
    
    motorista = Motorista.query.get_or_404(motorista_id)

    if request.method == 'POST':
        # --- VERIFICAÇÃO DE E-MAIL ÚNICO ---
        novo_email = request.form.get('email')
        # Se o e-mail foi alterado, verifica se o novo e-mail já existe em OUTRO usuário
        if novo_email != motorista.user.email:
            usuario_existente = User.query.filter(User.email == novo_email, User.id != motorista.user.id).first()
            if usuario_existente:
                flash('O e-mail informado já está em uso por outra conta.', 'danger')
                # Re-renderiza o formulário sem salvar, mantendo os dados que o usuário digitou
                return render_template('form_motorista.html', aba_ativa='motoristas', motorista=motorista)
        
        # --- ATUALIZAÇÃO DOS DADOS ---
        
        # 1. Atualizar dados do Motorista
        motorista.nome = request.form.get('nome')
        motorista.cpf_cnpj = request.form.get('cpf_cnpj')
        motorista.email = novo_email # Usa o novo e-mail verificado
        motorista.telefone = request.form.get('telefone')
        motorista.chave_pix = request.form.get('pix')
        motorista.status = request.form.get('status')
        motorista.veiculo_nome = request.form.get('veiculo')
        motorista.veiculo_placa = request.form.get('placa')
        motorista.veiculo_cor = request.form.get('cor')
        motorista.veiculo_ano = request.form.get('ano') or None
        motorista.veiculo_km = request.form.get('km_veiculo') or None
        motorista.veiculo_obs = request.form.get('observacoes')
        # ... (outros campos do motorista)

        # 2. Atualizar dados do User
        motorista.user.email = novo_email # Atualiza o e-mail de login
        nova_senha = request.form.get('senha')
        if nova_senha:
            motorista.user.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')

        db.session.commit()
        flash(f'Motorista "{motorista.nome}" atualizado com sucesso!', 'success')
        return redirect(url_for('admin.admin_dashboard', aba='motoristas'))

    # A lógica do GET permanece a mesma
    return render_template('form_motorista.html', aba_ativa='motoristas', motorista=motorista)


@admin_bp.route('/motoristas/excluir/<int:motorista_id>', methods=['POST'])
@login_required
def excluir_motorista(motorista_id):
    if current_user.role != 'admin':
        abort(403)

    motorista = Motorista.query.get_or_404(motorista_id)

    # if motorista.viagens: # Verificação de segurança futura
    #     flash('Não é possível excluir motoristas com viagens associadas.', 'danger')
    #     return redirect(url_for('admin.admin_dashboard', aba='motoristas'))

    # Apaga o User, e o Motorista será apagado em cascata
    user_para_excluir = motorista.user
    nome_motorista = motorista.nome

    db.session.delete(user_para_excluir)
    db.session.commit()

    flash(
        f'Motorista "{nome_motorista}" e seu usuário de acesso foram excluídos.', 'success')
    return redirect(url_for('admin.admin_dashboard', aba='motoristas'))


# =================================================================================================
# =================================================================================================
# =================================================================================================
# =================================================================================================
# ROTINAS DE PROCESSOS 
# ================================================================================================
# =================================================================================================
# =================================================================================================
# =================================================================================================



# =================================================================================================
# ROTA DE SOLICITAÇÕES - CORRIGIDA
# =================================================================================================

