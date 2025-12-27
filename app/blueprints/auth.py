"""
Blueprint de Autenticação Multi-Tenant
======================================

Gerencia login, logout e edição de perfil com suporte a múltiplas empresas.

Fluxo de Login:
1. Usuário informa: Licenciado, Email, Senha
2. Sistema busca empresa pelo slug do licenciado
3. Valida credenciais no banco correto
4. Define empresa ativa na sessão
5. Redireciona para dashboard apropriado
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import logging
import os

from .. import db
from ..models import User, Empresa, Motorista
from ..utils.admin_audit import log_audit, AuditAction
from ..config.db_helper import set_empresa_ativa, limpar_empresa_ativa, get_empresas_disponiveis_usuario
from ..config.database_config import db_manager
from flask import current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# Cria um Blueprint específico para autenticação
auth_bp = Blueprint('auth', __name__, url_prefix='/')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Rota de login multi-tenant.
    
    Fluxo:
    1. Valida licenciado (slug da empresa)
    2. Determina qual banco consultar
    3. Valida credenciais
    4. Valida permissão de acesso à empresa
    5. Define empresa ativa na sessão
    """
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        licenciado = request.form.get('licenciado', '').lower().strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # =====================================================================
        # PASSO 1: Validar Licenciado
        # =====================================================================
        if not licenciado:
            flash('Informe o licenciado.', 'warning')
            return render_template('login.html')
        
        # Buscar empresa no banco de referência
        # GOMOBI é um licenciado especial que aponta para LEAR (banco 1)
        slug_busca = licenciado
        if licenciado == 'gomobi':
            slug_busca = 'lear'  # GOMOBI usa banco da LEAR
        
        empresa = Empresa.query.filter_by(
            slug_licenciado=slug_busca,
            status='Ativo'
        ).first()
        
        if not empresa:
            # Se não encontrou, pode ser que 'gomobi' foi digitado mas LEAR não existe
            # Ou o licenciado digitado é inválido
            log_audit(
                action=AuditAction.LOGIN_FAILED,
                resource_type='User',
                resource_id=None,
                status='FAILED',
                severity='WARNING',
                user_id=None,
                user_name=email,
                user_role=None,
                reason=f'Licenciado inválido ou inativo: {licenciado}'
            )
            logger.warning(f"Login falhou: licenciado inválido '{licenciado}'")
            flash('Licenciado inválido ou inativo.', 'danger')
            return render_template('login.html')
        
        # =====================================================================
        # PASSO 2: Determinar qual banco consultar
        # =====================================================================
        user = None
        
        if licenciado == 'gomobi':
            # GOMOBI: Validar no Banco 1 (Admin, Operador, Motorista)
            user = User.query.filter_by(email=email).first()
            
        elif empresa.is_banco_local:
            # Empresa com banco local (ex: LEAR): Validar no Banco 1
            user = User.query.filter_by(email=email).first()
            
        else:
            # Empresa com banco remoto (ex: NSG): Validar no banco específico
            try:
                db_session = db_manager.get_session(empresa)
                user = db_session.query(User).filter_by(email=email).first()
            except Exception as e:
                logger.error(f"Erro ao conectar banco da empresa {empresa.nome}: {e}")
                flash('Erro ao conectar ao servidor. Tente novamente.', 'danger')
                return render_template('login.html')
        
        # =====================================================================
        # PASSO 3: Validar Credenciais
        # =====================================================================
        if not user:
            log_audit(
                action=AuditAction.LOGIN_FAILED,
                resource_type='User',
                resource_id=None,
                status='FAILED',
                severity='WARNING',
                user_id=None,
                user_name=email,
                user_role=None,
                reason=f'Usuário não encontrado para licenciado: {licenciado}'
            )
            logger.warning(f"Login falhou: usuário '{email}' não encontrado em '{licenciado}'")
            flash('Email ou senha inválidos.', 'danger')
            return render_template('login.html')
        
        if not check_password_hash(user.password, password):
            log_audit(
                action=AuditAction.LOGIN_FAILED,
                resource_type='User',
                resource_id=user.id,
                status='FAILED',
                severity='WARNING',
                user_id=user.id,
                user_name=email,
                user_role=user.role,
                reason=f'Senha incorreta para licenciado: {licenciado}'
            )
            logger.warning(f"Login falhou: senha incorreta para '{email}' em '{licenciado}'")
            flash('Email ou senha inválidos.', 'danger')
            return render_template('login.html')
        
        # Verificar se usuário está ativo
        if not user.is_active:
            log_audit(
                action=AuditAction.LOGIN_FAILED,
                resource_type='User',
                resource_id=user.id,
                status='FAILED',
                severity='WARNING',
                user_id=user.id,
                user_name=email,
                user_role=user.role,
                reason='Usuário inativo'
            )
            logger.warning(f"Login falhou: usuário '{email}' está inativo")
            flash('Sua conta está desativada. Contate o administrador.', 'danger')
            return render_template('login.html')
        
        # =====================================================================
        # PASSO 4: Validar Permissão de Acesso à Empresa
        # =====================================================================
        if licenciado == 'gomobi':
            # GOMOBI: Apenas Admin, Operador e Motorista
            if user.role not in ['admin', 'operador', 'motorista']:
                logger.warning(f"Login falhou: {user.role} tentou usar licenciado 'gomobi'")
                flash('Use o licenciado da sua empresa para acessar.', 'warning')
                return render_template('login.html')
            
            # Para motorista via GOMOBI, verificar se tem empresas_acesso
            if user.role == 'motorista' and user.motorista:
                if not user.motorista.empresas_acesso:
                    logger.warning(f"Motorista '{email}' sem empresas_acesso configurado")
                    flash('Seu acesso ainda não foi configurado. Contate o administrador.', 'warning')
                    return render_template('login.html')
                
                # Definir empresa padrão do motorista
                empresa_padrao_slug = user.motorista.empresa_padrao_slug
                if empresa_padrao_slug:
                    empresa = Empresa.query.filter_by(slug_licenciado=empresa_padrao_slug).first()
                else:
                    # Usar primeira empresa da lista
                    primeiro_slug = user.motorista.get_empresas_lista()[0]
                    empresa = Empresa.query.filter_by(slug_licenciado=primeiro_slug).first()
                
                if not empresa:
                    logger.error(f"Empresa padrão não encontrada para motorista '{email}'")
                    flash('Erro de configuração. Contate o administrador.', 'danger')
                    return render_template('login.html')
        
        else:
            # Outras empresas: Verificar permissão específica
            if user.role == 'motorista':
                # Motorista: Verificar empresas_acesso
                if user.motorista and not user.motorista.tem_acesso_empresa(licenciado):
                    logger.warning(f"Motorista '{email}' sem acesso à empresa '{licenciado}'")
                    flash('Você não tem acesso a esta empresa.', 'danger')
                    return render_template('login.html')
                    
            elif user.role in ['gerente', 'supervisor']:
                # Gerente/Supervisor: Verificar empresas_acesso do User
                if not user.tem_acesso_empresa(licenciado):
                    logger.warning(f"{user.role} '{email}' sem acesso à empresa '{licenciado}'")
                    flash('Você não tem acesso a esta empresa.', 'danger')
                    return render_template('login.html')
        
        # =====================================================================
        # PASSO 5: Login Bem-Sucedido
        # =====================================================================
        login_user(user)
        set_empresa_ativa(empresa)
        
        log_audit(
            action=AuditAction.LOGIN_SUCCESS,
            resource_type='User',
            resource_id=user.id,
            status='SUCCESS',
            severity='INFO',
            user_id=user.id,
            user_name=user.email,
            user_role=user.role,
            reason=f'Login via licenciado: {licenciado} | Empresa: {empresa.nome}'
        )
        
        logger.info(f"Login bem-sucedido: {email} ({user.role}) -> Empresa: {empresa.nome}")
        
        return redirect(url_for('home'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Rota de logout.
    
    Limpa sessão do usuário e empresa ativa.
    """
    # Captura informações do usuário ANTES do logout
    user_id = current_user.id
    user_email = current_user.email
    user_role = current_user.role
    empresa_slug = session.get('empresa_ativa_slug', 'N/A')

    # Limpa todas as mensagens flash antigas da sessão
    session.pop('_flashes', None)
    
    # Limpa empresa ativa
    limpar_empresa_ativa()

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
        user_role=user_role,
        reason=f'Logout da empresa: {empresa_slug}'
    )
    
    logger.info(f"Logout: {user_email} ({user_role})")

    # Adiciona apenas a mensagem de logout
    flash('Você saiu da sua conta.', 'success')

    return redirect(url_for('auth.login'))


@auth_bp.route('/trocar-empresa', methods=['POST'])
@login_required
def trocar_empresa():
    """
    Rota para trocar empresa ativa (para Admin, Operador e Motoristas multi-empresa).
    
    Recebe JSON: {"empresa_slug": "nsg"}
    Retorna JSON: {"success": true, "message": "...", "empresa_nome": "..."}
    """
    data = request.get_json()
    
    if not data or 'empresa_slug' not in data:
        return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
    
    empresa_slug = data['empresa_slug'].lower().strip()
    
    # Buscar empresa
    empresa = Empresa.query.filter_by(
        slug_licenciado=empresa_slug,
        status='Ativo'
    ).first()
    
    if not empresa:
        return jsonify({'success': False, 'message': 'Empresa não encontrada'}), 404
    
    # Validar acesso
    if current_user.role == 'motorista':
        if not current_user.motorista or not current_user.motorista.tem_acesso_empresa(empresa_slug):
            logger.warning(f"Motorista '{current_user.email}' tentou trocar para empresa sem acesso: {empresa_slug}")
            return jsonify({'success': False, 'message': 'Você não tem acesso a esta empresa'}), 403
    
    elif current_user.role not in ['admin', 'operador']:
        if not current_user.tem_acesso_empresa(empresa_slug):
            logger.warning(f"Usuário '{current_user.email}' tentou trocar para empresa sem acesso: {empresa_slug}")
            return jsonify({'success': False, 'message': 'Você não tem acesso a esta empresa'}), 403
    
    # Trocar empresa
    empresa_anterior = session.get('empresa_ativa_nome', 'N/A')
    set_empresa_ativa(empresa)
    
    # Log de auditoria
    log_audit(
        action=AuditAction.UPDATE,
        resource_type='Session',
        resource_id=current_user.id,
        status='SUCCESS',
        severity='INFO',
        reason=f'Trocou de empresa: {empresa_anterior} -> {empresa.nome}'
    )
    
    logger.info(f"Troca de empresa: {current_user.email} -> {empresa.nome}")
    
    return jsonify({
        'success': True, 
        'message': f'Empresa trocada para {empresa.nome}',
        'empresa_nome': empresa.nome,
        'empresa_slug': empresa.slug_licenciado
    })


@auth_bp.route('/empresas-disponiveis', methods=['GET'])
@login_required
def empresas_disponiveis():
    """
    Retorna lista de empresas disponíveis para o usuário atual.
    
    Usado pelo seletor de empresa no frontend.
    """
    empresas = get_empresas_disponiveis_usuario()
    empresa_ativa_slug = session.get('empresa_ativa_slug')
    
    return jsonify({
        'success': True,
        'empresas': [
            {
                'id': e.id,
                'nome': e.nome,
                'slug': e.slug_licenciado,
                'ativa': e.slug_licenciado == empresa_ativa_slug
            }
            for e in empresas
        ],
        'empresa_ativa_slug': empresa_ativa_slug
    })


@auth_bp.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    """
    Rota para edição de perfil do usuário.
    """
    if request.method == 'POST':
        mudancas = {}
        senha_alterada = False

        # Verifica se a senha foi alterada
        nova_senha = request.form.get('nova_senha')
        if nova_senha:
            current_user.password = generate_password_hash(
                nova_senha, method='pbkdf2:sha256')
            senha_alterada = True
            mudancas['senha'] = {'before': '***', 'after': '*** (alterada)'}

        # Verifica se o email foi alterado
        novo_email = request.form.get('email')
        if novo_email and novo_email != current_user.email:
            mudancas['email'] = {
                'before': current_user.email, 'after': novo_email}
            current_user.email = novo_email

        # --- LÓGICA PARA UPLOAD DA FOTO ---
        foto = request.files.get('foto_perfil')

        # Se o usuário enviou um novo arquivo
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            extensao = filename.rsplit('.', 1)[1].lower()
            nome_arquivo_unico = f"user_{current_user.id}.{extensao}"
            caminho_salvar = os.path.join(
                current_app.config['UPLOAD_FOLDER'], nome_arquivo_unico)
            foto.save(caminho_salvar)

            mudancas['foto_perfil'] = {
                'before': current_user.foto_perfil, 'after': nome_arquivo_unico}
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


@auth_bp.route('/testar-conexao-banco', methods=['POST'])
@login_required
def testar_conexao_banco():
    """
    Testa conexão com banco de dados remoto.
    
    Usado pelo formulário de cadastro de empresa para validar
    as credenciais antes de salvar.
    
    Recebe JSON: {db_host, db_port, db_name, db_user, db_pass}
    Retorna JSON: {success: bool, message: str}
    """
    # Apenas Admin pode testar conexões
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Dados inválidos'}), 400
    
    # Validar campos obrigatórios
    required = ['db_host', 'db_name', 'db_user', 'db_pass']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'Campo {field} é obrigatório'}), 400
    
    # Construir URL de conexão
    db_port = data.get('db_port', 5432)
    db_url = f"postgresql://{data['db_user']}:{data['db_pass']}@{data['db_host']}:{db_port}/{data['db_name']}"
    
    try:
        from sqlalchemy import create_engine, text
        
        # Criar engine temporária para teste
        engine = create_engine(db_url, connect_args={'connect_timeout': 10})
        
        # Testar conexão
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        engine.dispose()
        
        logger.info(f"Teste de conexão bem-sucedido: {data['db_host']}/{data['db_name']}")
        return jsonify({'success': True, 'message': 'Conexão estabelecida com sucesso!'})
        
    except Exception as e:
        error_msg = str(e)
        
        # Simplificar mensagens de erro comuns
        if 'could not connect' in error_msg.lower():
            error_msg = 'Não foi possível conectar ao servidor. Verifique o host e a porta.'
        elif 'password authentication failed' in error_msg.lower():
            error_msg = 'Usuário ou senha incorretos.'
        elif 'database' in error_msg.lower() and 'does not exist' in error_msg.lower():
            error_msg = 'Banco de dados não encontrado.'
        elif 'timeout' in error_msg.lower():
            error_msg = 'Tempo limite excedido. Verifique se o servidor está acessível.'
        
        logger.error(f"Teste de conexão falhou: {error_msg}")
        return jsonify({'success': False, 'message': error_msg})
