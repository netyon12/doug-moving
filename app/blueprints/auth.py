from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

from .. import db
from ..models import User, Supervisor, Colaborador, Motorista, Bloco, Viagem, Solicitacao
from ..utils.admin_audit import log_audit, AuditAction
from io import StringIO
import csv
import os
from flask import current_app # Para acessar app.config['UPLOAD_FOLDER']
from werkzeug.utils import secure_filename

# Cria um Blueprint específico para autenticação
auth_bp = Blueprint('auth', __name__, url_prefix='/') # ou sem prefixo


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home')) 
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            
            # AUDITORIA: Login bem-sucedido
            log_audit(
                action=AuditAction.LOGIN_SUCCESS,
                resource_type='User',
                resource_id=user.id,
                status='SUCCESS',
                severity='INFO',
                user_id=user.id,
                user_name=user.email,
                user_role=user.role
            )
            
            return redirect(url_for('home')) 
        else:
            # AUDITORIA: Login falhou
            log_audit(
                action=AuditAction.LOGIN_FAILED,
                resource_type='User',
                resource_id=None,
                status='FAILED',
                severity='WARNING',
                user_id=None,
                user_name=email,
                user_role=None,
                reason=f'Tentativa de login com email: {email}'
            )
            
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
            
    return render_template('login.html')



@auth_bp.route('/logout')
@login_required
def logout():
    from flask import session
    
    # Captura informações do usuário ANTES do logout
    user_id = current_user.id
    user_email = current_user.email
    user_role = current_user.role
    
    # Limpa todas as mensagens flash antigas da sessão
    session.pop('_flashes', None)
    
    # Faz o logout
    logout_user()
    
    # AUDITORIA: Logout
    log_audit(
        action=AuditAction.LOGOUT,
        resource_type='User',
        resource_id=user_id,
        status='SUCCESS',
        severity='INFO',
        user_id=user_id,
        user_name=user_email,
        user_role=user_role
    )
    
    # Adiciona apenas a mensagem de logout
    flash('Você saiu da sua conta.', 'success')
    
    return redirect(url_for('auth.login'))




@auth_bp.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    if request.method == 'POST':
        mudancas = {}
        senha_alterada = False
        
        # Verifica se a senha foi alterada
        nova_senha = request.form.get('nova_senha')
        if nova_senha:
            current_user.password = generate_password_hash(nova_senha, method='pbkdf2:sha256')
            senha_alterada = True
            mudancas['senha'] = {'before': '***', 'after': '*** (alterada)'}
        
        # Verifica se o email foi alterado
        novo_email = request.form.get('email')
        if novo_email and novo_email != current_user.email:
            mudancas['email'] = {'before': current_user.email, 'after': novo_email}
            current_user.email = novo_email

        # --- LÓGICA PARA UPLOAD DA FOTO ---
        foto = request.files.get('foto_perfil')
        
        # Se o usuário enviou um novo arquivo
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            extensao = filename.rsplit('.', 1)[1].lower()
            nome_arquivo_unico = f"user_{current_user.id}.{extensao}"
            caminho_salvar = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo_unico)
            foto.save(caminho_salvar)
            
            mudancas['foto_perfil'] = {'before': current_user.foto_perfil, 'after': nome_arquivo_unico}
            current_user.foto_perfil = nome_arquivo_unico
            flash('Sua foto de perfil foi atualizada!', 'info')

        db.session.commit()
        
        # AUDITORIA: Atualização de perfil
        if mudancas:
            if senha_alterada:
                # Log específico para mudança de senha
                log_audit(
                    action=AuditAction.PASSWORD_CHANGE,
                    resource_type='User',
                    resource_id=current_user.id,
                    status='SUCCESS',
                    severity='WARNING',  # Mudança de senha é WARNING por segurança
                    changes=mudancas
                )
            else:
                # Log geral de atualização
                log_audit(
                    action=AuditAction.UPDATE,
                    resource_type='User',
                    resource_id=current_user.id,
                    status='SUCCESS',
                    severity='INFO',
                    changes=mudancas
                )
        
        flash('Seu perfil foi atualizado com sucesso!', 'success')
        return redirect(url_for('auth.editar_perfil'))

    return render_template('editar_perfil.html')