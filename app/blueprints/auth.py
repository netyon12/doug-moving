from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

from .. import db
from ..models import User, Supervisor, Colaborador, Motorista, Bloco, Viagem, Solicitacao
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
        # Correção: A rota 'home' não tem blueprint.
        return redirect(url_for('home')) 
    
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            # Correção: A rota 'home' não tem blueprint.
            return redirect(url_for('home')) 
        else:
            flash('Email ou senha inválidos. Tente novamente.', 'danger')
            
    return render_template('login.html')



@auth_bp.route('/logout')
@login_required
def logout():
    from flask import session
    
    # Limpa todas as mensagens flash antigas da sessão
    session.pop('_flashes', None)
    
    # Faz o logout
    logout_user()
    
    # Adiciona apenas a mensagem de logout
    flash('Você saiu da sua conta.', 'success')
    
    return redirect(url_for('auth.login'))




@auth_bp.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    if request.method == 'POST':
        # ... (toda a lógica de atualização de nome, e-mail e senha permanece a mesma) ...

        # --- NOVA LÓGICA PARA UPLOAD DA FOTO ---
        foto = request.files.get('foto_perfil')
        
        # Se o usuário enviou um novo arquivo
        if foto and foto.filename != '':
            # 1. Garante que o nome do arquivo é seguro
            filename = secure_filename(foto.filename)
            
            # 2. Cria um nome de arquivo único para evitar conflitos (ex: user_5.jpg)
            # Isso garante que cada usuário só pode ter uma foto, que é sobrescrita.
            extensao = filename.rsplit('.', 1)[1].lower()
            nome_arquivo_unico = f"user_{current_user.id}.{extensao}"
            
            # 3. Salva o arquivo na pasta de uploads
            caminho_salvar = os.path.join(current_app.config['UPLOAD_FOLDER'], nome_arquivo_unico)
            foto.save(caminho_salvar)
            
            # 4. Atualiza o nome do arquivo no banco de dados para o usuário
            current_user.foto_perfil = nome_arquivo_unico
            flash('Sua foto de perfil foi atualizada!', 'info')

        # ... (o db.session.commit() que já existe salvará a foto junto com o resto) ...
        
        db.session.commit()
        flash('Seu perfil foi atualizado com sucesso!', 'success')
        return redirect(url_for('auth.editar_perfil'))

    return render_template('editar_perfil.html')