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
from sqlalchemy.exc import IntegrityError
from io import StringIO
import io
import csv

from .. import db, cache
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp


@admin_bp.route('/colaboradores/cadastrar', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente', 'supervisor', 'operador'])
def cadastrar_colaborador():

    if request.method == 'POST':
        try:
            # Validação de campos obrigatórios
            nome = request.form.get('nome', '').strip()
            matricula = request.form.get('matricula', '').strip()
            status = request.form.get('status', '').strip()

            if not nome:
                return jsonify({'success': False, 'message': 'Nome é obrigatório'}), 400
            if not matricula:
                return jsonify({'success': False, 'message': 'Matrícula é obrigatória'}), 400
            if not status:
                return jsonify({'success': False, 'message': 'Status é obrigatório'}), 400

            # Lógica para pegar o ID da empresa e planta corretamente
            if current_user.role == 'supervisor':
                empresa_id = current_user.supervisor.empresa_id
                planta_id = request.form.get('planta_id')
                if not planta_id and current_user.supervisor.plantas:
                    planta_id = current_user.supervisor.plantas[0].id
            else:  # Para Admin e Gerente
                empresa_id = request.form.get('empresa_id')
                planta_id = request.form.get('planta_id')

            if not empresa_id:
                return jsonify({'success': False, 'message': 'Empresa é obrigatória'}), 400
            if not planta_id:
                return jsonify({'success': False, 'message': 'Planta é obrigatória'}), 400

            # Validação de matrícula duplicada
            print(f"[DEBUG] Verificando matrícula: '{matricula}'")
            colaborador_existente = Colaborador.query.filter_by(
                matricula=matricula).first()
            print(f"[DEBUG] Colaborador existente: {colaborador_existente}")
            if colaborador_existente:
                print(
                    f"[DEBUG] Matrícula duplicada encontrada: ID={colaborador_existente.id}, Nome={colaborador_existente.nome}")
                return jsonify({
                    'success': False,
                    'message': 'Já existe um colaborador com esta matrícula'
                }), 400
            print(f"[DEBUG] Matrícula '{matricula}' está disponível")

            # Validação do telefone
            telefone = request.form.get('telefone', '').replace(' ', '').replace(
                '-', '').replace('(', '').replace(')', '').replace('.', '')
            if telefone and (not telefone.isdigit() or len(telefone) != 11):
                return jsonify({
                    'success': False,
                    'message': 'O telefone deve conter exatamente 11 dígitos (DDD + número). Exemplo: 81988751618'
                }), 400

            novo_colaborador = Colaborador(
                nome=nome,
                matricula=matricula,
                empresa_id=empresa_id,
                planta_id=planta_id,
                status=status,
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

            return jsonify({
                'success': True,
                'message': f'Colaborador "{novo_colaborador.nome}" cadastrado com sucesso!',
                'redirect': url_for('admin.admin_dashboard', aba='colaboradores')
            })

        except Exception as e:
            db.session.rollback()

            # Tratamento de erros específicos
            print(f"[DEBUG] Exceção capturada: {type(e).__name__}: {str(e)}")
            error_message = 'Erro ao cadastrar colaborador'

            if 'unique constraint' in str(e).lower():
                if 'matricula' in str(e).lower():
                    error_message = 'Já existe um colaborador com esta matrícula'
                elif 'email' in str(e).lower():
                    error_message = 'Já existe um colaborador com este e-mail'
                else:
                    error_message = 'Já existe um colaborador com estes dados'
            elif 'not null' in str(e).lower():
                error_message = 'Todos os campos obrigatórios devem ser preenchidos'
            elif 'foreign key' in str(e).lower():
                error_message = 'Empresa ou Planta inválida'
            else:
                error_message = f'Erro ao cadastrar: {str(e)}'

            return jsonify({
                'success': False,
                'message': error_message
            }), 500

    # Lógica do GET: passa todos os dados para os dropdowns
    if current_user.role in ['admin', 'operador']:
        empresas = Empresa.query.all()
        plantas = Planta.query.all()
    elif current_user.role == 'gerente':
        empresas = [current_user.gerente.empresa]
        plantas = Planta.query.filter_by(
            empresa_id=current_user.gerente.empresa_id).all()
    else:  # Supervisor
        empresas = [current_user.supervisor.empresa]
        plantas = current_user.supervisor.plantas  # Múltiplas plantas

    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()

    return render_template(
        'colaborador/form_colaborador.html',
        aba_ativa='colaboradores',
        empresas=empresas,
        plantas=plantas,
        blocos=blocos,
        status_opcoes=Colaborador.STATUS_VALIDOS
    )


@admin_bp.route('/colaboradores/editar/<int:colaborador_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin', 'gerente', 'supervisor', 'operador'])
def editar_colaborador(colaborador_id):
    colaborador = Colaborador.query.get_or_404(colaborador_id)

    if current_user.role not in ['admin', 'supervisor', 'gerente', 'operador']:
        abort(403)

    if request.method == 'POST':
        try:
            # Validação de campos obrigatórios
            nome = request.form.get('nome', '').strip()
            matricula = request.form.get('matricula', '').strip()
            status = request.form.get('status', '').strip()

            if not nome:
                return jsonify({'success': False, 'message': 'Nome é obrigatório'}), 400
            if not matricula:
                return jsonify({'success': False, 'message': 'Matrícula é obrigatória'}), 400
            if not status:
                return jsonify({'success': False, 'message': 'Status é obrigatório'}), 400

            if current_user.role == 'supervisor':
                colaborador.empresa_id = current_user.supervisor.empresa_id
                planta_id = request.form.get('planta_id')
                if not planta_id and current_user.supervisor.plantas:
                    planta_id = current_user.supervisor.plantas[0].id
                colaborador.planta_id = planta_id
            else:
                empresa_id = request.form.get('empresa_id')
                planta_id = request.form.get('planta_id')

                if not empresa_id:
                    return jsonify({'success': False, 'message': 'Empresa é obrigatória'}), 400
                if not planta_id:
                    return jsonify({'success': False, 'message': 'Planta é obrigatória'}), 400

                colaborador.empresa_id = empresa_id
                colaborador.planta_id = planta_id

            # Validação do telefone
            telefone = request.form.get('telefone', '').replace(' ', '').replace(
                '-', '').replace('(', '').replace(')', '').replace('.', '')
            if telefone and (not telefone.isdigit() or len(telefone) != 11):
                return jsonify({
                    'success': False,
                    'message': 'O telefone deve conter exatamente 11 dígitos (DDD + número). Exemplo: 81988751618'
                }), 400

            colaborador.nome = nome
            colaborador.matricula = matricula
            colaborador.status = status
            colaborador.endereco = request.form.get('endereco')
            colaborador.nro = request.form.get('nro')
            colaborador.bairro = request.form.get('bairro')
            colaborador.cidade = request.form.get('cidade')
            colaborador.uf = request.form.get('uf')
            colaborador.telefone = telefone
            colaborador.email = request.form.get('email')
            colaborador.bloco_id = request.form.get('bloco_id') or None

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Colaborador "{colaborador.nome}" atualizado com sucesso!',
                'redirect': url_for('admin.admin_dashboard', aba='colaboradores')
            })

        except Exception as e:
            db.session.rollback()

            # Tratamento de erros específicos
            error_message = 'Erro ao atualizar colaborador'

            if 'unique constraint' in str(e).lower():
                if 'matricula' in str(e).lower():
                    error_message = 'Já existe outro colaborador com esta matrícula'
                elif 'email' in str(e).lower():
                    error_message = 'Já existe outro colaborador com este e-mail'
                else:
                    error_message = 'Já existe outro colaborador com estes dados'
            elif 'not null' in str(e).lower():
                error_message = 'Todos os campos obrigatórios devem ser preenchidos'
            elif 'foreign key' in str(e).lower():
                error_message = 'Empresa ou Planta inválida'
            else:
                error_message = f'Erro ao atualizar: {str(e)}'

            return jsonify({
                'success': False,
                'message': error_message
            }), 500

    # Lógica do GET para edição
    if current_user.role in ['admin', 'operador']:
        empresas = Empresa.query.all()
        plantas = Planta.query.all()
    else:  # Gerente ou Supervisor
        empresas = [current_user.empresa]
        plantas = [current_user.planta]

    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()

    return render_template(
        'colaborador/form_colaborador.html',
        aba_ativa='colaboradores',
        colaborador=colaborador,
        empresas=empresas,
        plantas=plantas,
        blocos=blocos,
        status_opcoes=Colaborador.STATUS_VALIDOS
    )


@admin_bp.route('/colaboradores/excluir/<int:colaborador_id>', methods=['POST'])
@login_required
def excluir_colaborador(colaborador_id):
    # Apenas o admin pode excluir
    if current_user.role not in ['admin', 'operador']:
        abort(403)

    colaborador = Colaborador.query.get_or_404(colaborador_id)

    #Verificação de segurança (opcional, mas recomendada): impede a exclusão se tiver solicitações associadas
    if Solicitacao.query.filter_by(colaborador_id=colaborador.id).first():
         flash(f'Não é possível excluir o colaborador "{colaborador.nome}", pois ele possui solicitações de transporte associadas.', 'danger')
         return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

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
# @cache.cached(timeout=3600, query_string=True) Cache que guarda por 1 hora (3600 segundos) os bairros.
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
        texto_sem_acento = ''.join(
            c for c in texto_sem_acento if unicodedata.category(c) != 'Mn')
        # Remove pontos e espaços duplos, converte para minúsculas
        texto_limpo = texto_sem_acento.lower().replace(
            '.', '').replace('  ', ' ').strip()
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
    if current_user.role not in ['admin', 'operador']:
        abort(403)

    if request.method == 'POST':
        try:
            # Validações
            email = request.form.get('email')
            senha = request.form.get('senha')
            nome = request.form.get('nome')
            placa = request.form.get('placa')

            # Validar campos obrigatórios
            if not all([email, senha, nome, placa]):
                return jsonify({
                    'success': False,
                    'message': 'Preencha todos os campos obrigatórios (email, senha, nome, placa)'
                }), 400

            # Validar email duplicado
            if User.query.filter_by(email=email).first():
                return jsonify({
                    'success': False,
                    'message': 'Este e-mail de acesso já está em uso'
                }), 400

            # Validar placa duplicada
            motorista_existente = Motorista.query.filter_by(
                veiculo_placa=placa).first()
            if motorista_existente:
                return jsonify({
                    'success': False,
                    'message': f'Já existe um motorista com a placa {placa}'
                }), 400

            # 1. Criar User
            hashed_password = generate_password_hash(
                senha, method='pbkdf2:sha256')
            new_user = User(
                email=email, password=hashed_password, role='motorista')
            db.session.add(new_user)
            db.session.flush()  # Gera o ID do user

            # 2. Criar Motorista
            novo_motorista = Motorista(
                user_id=new_user.id,
                nome=nome,
                cpf_cnpj=request.form.get('cpf_cnpj'),
                endereco=request.form.get('endereco'),
                nro=request.form.get('nro'),
                bairro=request.form.get('bairro'),
                cidade=request.form.get('cidade'),
                uf=request.form.get('uf'),
                telefone=request.form.get('telefone'),
                email=email,
                chave_pix=request.form.get('pix'),
                status=request.form.get('status', 'Ativo'),
                # Campos do veículo
                veiculo_nome=request.form.get('veiculo'),
                veiculo_placa=placa,
                veiculo_cor=request.form.get('cor'),
                veiculo_ano=request.form.get('ano') or None,
                veiculo_km=request.form.get('km_veiculo') or None,
                veiculo_obs=request.form.get('observacoes')
            )
            db.session.add(novo_motorista)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Motorista "{novo_motorista.nome}" cadastrado com sucesso!',
                'redirect': url_for('admin.admin_dashboard', aba='motoristas')
            })

        except IntegrityError as e:
            db.session.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)

            if 'unique constraint' in error_msg.lower():
                if 'email' in error_msg.lower():
                    return jsonify({
                        'success': False,
                        'message': 'Este e-mail já está cadastrado'
                    }), 400
                elif 'placa' in error_msg.lower():
                    return jsonify({
                        'success': False,
                        'message': 'Esta placa já está cadastrada'
                    }), 400

            return jsonify({
                'success': False,
                'message': 'Erro ao cadastrar motorista. Verifique os dados e tente novamente.'
            }), 500

        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Erro ao cadastrar motorista: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Erro ao cadastrar motorista'
            }), 500

    # GET: renderizar formulário
    return render_template('motorista/form_motorista.html', aba_ativa='motoristas')


@admin_bp.route('/motoristas/editar/<int:motorista_id>', methods=['GET', 'POST'])
@login_required
def editar_motorista(motorista_id):
    if current_user.role not in ['admin', 'operador']:
        abort(403)

    motorista = Motorista.query.get_or_404(motorista_id)

    if request.method == 'POST':
        try:
            # Validações
            novo_email = request.form.get('email')
            nova_placa = request.form.get('placa')

            # Validar campos obrigatórios
            if not all([novo_email, request.form.get('nome'), nova_placa]):
                return jsonify({
                    'success': False,
                    'message': 'Preencha todos os campos obrigatórios (email, nome, placa)'
                }), 400

            # Validar email duplicado (se foi alterado)
            if novo_email != motorista.user.email:
                usuario_existente = User.query.filter(
                    User.email == novo_email,
                    User.id != motorista.user.id
                ).first()
                if usuario_existente:
                    return jsonify({
                        'success': False,
                        'message': 'O e-mail informado já está em uso por outra conta'
                    }), 400

            # Validar placa duplicada (se foi alterada)
            if nova_placa != motorista.veiculo_placa:
                motorista_existente = Motorista.query.filter(
                    Motorista.veiculo_placa == nova_placa,
                    Motorista.id != motorista_id
                ).first()
                if motorista_existente:
                    return jsonify({
                        'success': False,
                        'message': f'Já existe outro motorista com a placa {nova_placa}'
                    }), 400

            # 1. Atualizar dados do Motorista
            motorista.nome = request.form.get('nome')
            motorista.cpf_cnpj = request.form.get('cpf_cnpj')
            motorista.email = novo_email
            motorista.telefone = request.form.get('telefone')
            motorista.chave_pix = request.form.get('pix')
            motorista.status = request.form.get('status', 'Ativo')
            motorista.veiculo_nome = request.form.get('veiculo')
            motorista.veiculo_placa = nova_placa
            motorista.veiculo_cor = request.form.get('cor')
            motorista.veiculo_ano = request.form.get('ano') or None
            motorista.veiculo_km = request.form.get('km_veiculo') or None
            motorista.veiculo_obs = request.form.get('observacoes')

            # 2. Atualizar dados do User
            motorista.user.email = novo_email
            nova_senha = request.form.get('senha')
            if nova_senha:
                motorista.user.password = generate_password_hash(
                    nova_senha, method='pbkdf2:sha256')

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Motorista "{motorista.nome}" atualizado com sucesso!',
                'redirect': url_for('admin.admin_dashboard', aba='motoristas')
            })

        except IntegrityError as e:
            db.session.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)

            if 'unique constraint' in error_msg.lower():
                if 'email' in error_msg.lower():
                    return jsonify({
                        'success': False,
                        'message': 'Este e-mail já está cadastrado'
                    }), 400
                elif 'placa' in error_msg.lower():
                    return jsonify({
                        'success': False,
                        'message': 'Esta placa já está cadastrada'
                    }), 400

            return jsonify({
                'success': False,
                'message': 'Erro ao atualizar motorista. Verifique os dados e tente novamente.'
            }), 500

        except Exception as e:
            db.session.rollback()
            print(f"[ERRO] Erro ao editar motorista: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Erro ao atualizar motorista'
            }), 500

    # GET: renderizar formulário
    return render_template('motorista/form_motorista.html', aba_ativa='motoristas', motorista=motorista)


@admin_bp.route('/motoristas/excluir/<int:motorista_id>', methods=['POST'])
@login_required
def excluir_motorista(motorista_id):
    if current_user.role not in ['admin', 'operador']:
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
