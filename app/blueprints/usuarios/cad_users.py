from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError

from ... import db
from ...models import User, Gerente, Supervisor, Motorista
from ...decorators import role_required
from ...config.tenant_utils import query_tenant  # ← CORREÇÃO: Importar query_tenant

# Define o Blueprint
cad_users_bp = Blueprint('cad_users', __name__, url_prefix='/configuracoes/usuarios')

# =============================================================================
# CONSTANTES
# =============================================================================
ROLES_VALIDOS = ['admin', 'gerente', 'supervisor', 'motorista', 'operador']

# =============================================================================
# ROTAS DE VISUALIZAÇÃO E LISTAGEM (READ)
# =============================================================================

@cad_users_bp.route('/')
@login_required
@role_required('admin', 'operador')
def listar_usuarios():
    """Lista todos os usuários do sistema."""
    usuarios = query_tenant(User).order_by(User.email).all()  # ← CORREÇÃO: Usar query_tenant
    return render_template('config/cad_users.html', usuarios=usuarios, roles=ROLES_VALIDOS)

# =============================================================================
# ROTAS DE CRIAÇÃO (CREATE)
# =============================================================================

@cad_users_bp.route('/incluir', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operador')
def incluir_usuario():
    """Inclui um novo usuário no sistema."""
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')
        role = request.form.get('role')
        is_active = request.form.get('is_active') == 'on'

        if not email or not password or not role:
            flash('Todos os campos obrigatórios devem ser preenchidos.', 'danger')
            return redirect(url_for('cad_users.incluir_usuario'))

        if role not in ROLES_VALIDOS:
            flash('Perfil de usuário inválido.', 'danger')
            return redirect(url_for('cad_users.incluir_usuario'))

        # 1. Verifica se o email já existe
        if query_tenant(User).filter_by(email=email).first():
            flash('Já existe um usuário cadastrado com este e-mail.', 'danger')
            return redirect(url_for('cad_users.incluir_usuario'))

        try:
            # 2. Cria o novo usuário
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            novo_usuario = User(
                email=email,
                password=hashed_password,
                role=role,
                is_active=is_active
            )
            db.session.add(novo_usuario)
            db.session.commit()
            flash(f'Usuário {email} ({role}) incluído com sucesso!', 'success')
            return redirect(url_for('cad_users.listar_usuarios'))

        except IntegrityError:
            db.session.rollback()
            flash('Erro de integridade ao incluir o usuário. Verifique se o e-mail já existe.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao incluir usuário: {str(e)}', 'danger')

    # Se for GET, apenas renderiza o formulário (o mesmo template de listagem será usado com modal)
    # ou redireciona para a listagem se o formulário for integrado
    return redirect(url_for('cad_users.listar_usuarios'))

# =============================================================================
# ROTAS DE EDIÇÃO (UPDATE)
# =============================================================================

@cad_users_bp.route('/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operador')
def editar_usuario(user_id):
    """Edita um usuário existente."""
    usuario = query_tenant(User).get_or_404(user_id)

    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')
        role = request.form.get('role')
        is_active = request.form.get('is_active') == 'on'

        if not email or not role:
            flash('E-mail e Perfil são obrigatórios.', 'danger')
            return redirect(url_for('cad_users.listar_usuarios'))

        if role not in ROLES_VALIDOS:
            flash('Perfil de usuário inválido.', 'danger')
            return redirect(url_for('cad_users.listar_usuarios'))

        try:
            # 1. Verifica unicidade do email (se mudou)
            if email != usuario.email and query_tenant(User).filter_by(email=email).first():
                flash('Já existe outro usuário cadastrado com este e-mail.', 'danger')
                return redirect(url_for('cad_users.listar_usuarios'))

            # 2. Aplica as alterações
            usuario.email = email
            usuario.role = role
            usuario.is_active = is_active

            # 3. Atualiza a senha se um novo valor for fornecido
            if password:
                usuario.password = generate_password_hash(password, method='pbkdf2:sha256')

            db.session.commit()
            flash(f'Usuário {usuario.email} atualizado com sucesso!', 'success')
            return redirect(url_for('cad_users.listar_usuarios'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar usuário: {str(e)}', 'danger')

    # Se for GET, apenas renderiza o formulário (o mesmo template de listagem será usado com modal)
    return redirect(url_for('cad_users.listar_usuarios'))


# =============================================================================
# ROTAS DE EXCLUSÃO (DELETE)
# =============================================================================

@cad_users_bp.route('/excluir/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin') # Apenas Admin pode excluir
def excluir_usuario(user_id):
    """Exclui um usuário, verificando vínculos."""
    usuario = query_tenant(User).get_or_404(user_id)

    # 1. Verifica vínculos (Regra de Negócio)
    if usuario.gerente or usuario.supervisor or usuario.motorista:
        flash(f'Usuário {usuario.email} possui vínculo ativo com Gerente, Supervisor ou Motorista. Exclua o cadastro de origem primeiro.', 'danger')
        return redirect(url_for('cad_users.listar_usuarios'))

    # 2. Exclui o usuário
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash(f'Usuário {usuario.email} excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir usuário: {str(e)}', 'danger')

    return redirect(url_for('cad_users.listar_usuarios'))
