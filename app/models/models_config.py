"""
Modelos de Configuração e Auditoria
===================================

Classes relacionadas a autenticação, configuração e auditoria:
- User: Usuários do sistema com autenticação
- Configuracao: Configurações globais do sistema
- AuditLog: Log de auditoria geral do sistema
- ViagemAuditoria: Log específico de auditoria de viagens
"""

from app import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'user'  # É uma boa prática nomear a tabela explicitamente
    id = db.Column(db.Integer, primary_key=True)
    # 'email' é o login/usuário
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # 'admin', 'gerente', 'supervisor', 'motorista', 'operador'
    role = db.Column(db.String(20), nullable=False)
    foto_perfil = db.Column(
        db.String(100), nullable=False, default='default.jpg')
    # NOVO CAMPO: Status de Ativação
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # --- RELACIONAMENTOS COM OS PERFIS ---
    # Cada usuário pode ser, no máximo, um destes perfis.
    gerente = db.relationship(
        'Gerente', back_populates='user', uselist=False, cascade="all, delete-orphan")
    supervisor = db.relationship(
        'Supervisor', back_populates='user', uselist=False, cascade="all, delete-orphan")
    motorista = db.relationship(
        'Motorista', back_populates='user', uselist=False, cascade="all, delete-orphan")

    # --- PROPRIEDADES DINÂMICAS PARA ACESSO FÁCIL AOS DADOS ---
    # Estas propriedades permitem usar 'current_user.nome' ou 'current_user.empresa'
    # em qualquer template, independentemente do perfil do usuário logado.

    @property
    def nome(self):
        """Retorna o nome associado ao perfil do usuário."""
        if self.role == 'gerente' and self.gerente:
            return self.gerente.nome
        if self.role == 'supervisor' and self.supervisor:
            return self.supervisor.nome
        if self.role == 'motorista' and self.motorista:
            return self.motorista.nome
        if self.role == 'admin':
            return "Administrador"
        if self.role == 'operador':
            return "Operador"
        return self.email  # Fallback

    @property
    def telefone(self):
        """Retorna o telefone associado ao perfil do usuário."""
        if self.role == 'gerente' and self.gerente:
            # O modelo Gerente não tem telefone, mas podemos adicionar se necessário.
            # Por enquanto, retornamos o do supervisor ou motorista.
            return ""
        if self.role == 'supervisor' and self.supervisor:
            return self.supervisor.telefone
        if self.role == 'motorista' and self.motorista:
            return self.motorista.telefone
        return ""

    @property
    def empresa(self):
        """Retorna o objeto Empresa associado ao perfil do usuário (se aplicável)."""
        if self.role in ['gerente', 'supervisor'] and hasattr(self, self.role) and getattr(self, self.role):
            return getattr(self, self.role).empresa
        return None

    @property
    def planta(self):
        """Retorna o objeto Planta associado ao perfil do usuário (se aplicável)."""
        if self.role in ['gerente', 'supervisor'] and hasattr(self, self.role) and getattr(self, self.role):
            return getattr(self, self.role).planta
        return None

    def __repr__(self):
        return f'<User {self.email} - {self.role}>'


class Configuracao(db.Model):
    """Armazena configurações globais do sistema como pares de chave-valor."""
    __tablename__ = 'configuracao'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Configuracao {self.chave}={self.valor}>'


class AuditLog(db.Model):
    """
    Tabela principal de auditoria para registrar todas as operações do sistema.

    Segue padrões de conformidade: GDPR, SOX, ISO 27001, LGPD

    Campos essenciais:
    - Quem fez (user_id, user_name)
    - O que fez (action, resource_type, resource_id)
    - Quando fez (timestamp)
    - Como fez (ip_address, user_agent, method)
    - Resultado (status, error_message)
    - Detalhes (changes, reason)
    """
    __tablename__ = 'audit_log'

    # Identificação
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.utcnow, index=True)

    # Usuário que executou a ação
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True, index=True)
    # Desnormalizado para histórico
    user_name = db.Column(db.String(100), nullable=True)
    # admin, motorista, supervisor, etc.
    user_role = db.Column(db.String(50), nullable=True)

    # Ação executada
    # CREATE, UPDATE, DELETE, LOGIN, etc.
    action = db.Column(db.String(50), nullable=False, index=True)
    # Viagem, User, Motorista, etc.
    resource_type = db.Column(db.String(50), nullable=False, index=True)
    resource_id = db.Column(db.Integer, nullable=True,
                            index=True)  # ID do recurso afetado

    # Status da operação
    status = db.Column(db.String(20), nullable=False,
                       default='SUCCESS')  # SUCCESS, FAILED, ERROR

    # Contexto da requisição
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 ou IPv6
    # Navegador/dispositivo
    user_agent = db.Column(db.String(255), nullable=True)
    # GET, POST, PUT, DELETE
    request_method = db.Column(db.String(10), nullable=True)
    route = db.Column(db.String(255), nullable=True)  # Rota/endpoint acessado
    module = db.Column(db.String(50), nullable=True)  # Blueprint/módulo

    # Detalhes da mudança
    changes = db.Column(db.Text, nullable=True)  # JSON com before/after
    # Motivo da ação (quando aplicável)
    reason = db.Column(db.Text, nullable=True)
    # Mensagem de erro (se falhou)
    error_message = db.Column(db.Text, nullable=True)

    # Metadados adicionais
    session_id = db.Column(db.String(100), nullable=True)  # ID da sessão
    # Tempo de execução em ms
    duration_ms = db.Column(db.Integer, nullable=True)
    # INFO, WARNING, ERROR, CRITICAL
    severity = db.Column(db.String(20), nullable=False, default='INFO')

    # Relacionamentos
    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.id}: {self.user_name} - {self.action} {self.resource_type}#{self.resource_id}>'

    def to_dict(self):
        """Converte o log para dicionário."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'user_role': self.user_role,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'status': self.status,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'request_method': self.request_method,
            'route': self.route,
            'module': self.module,
            'changes': self.changes,
            'reason': self.reason,
            'error_message': self.error_message,
            'session_id': self.session_id,
            'duration_ms': self.duration_ms,
            'severity': self.severity
        }


class ViagemAuditoria(db.Model):
    """
    Tabela específica para auditoria de viagens.

    Registra todo o histórico de mudanças de uma viagem:
    - Criação
    - Aceitação por motorista
    - Início da viagem
    - Finalização
    - Cancelamento/Desassociação
    - Mudanças de status

    Permite rastreabilidade completa do ciclo de vida da viagem.
    """
    __tablename__ = 'viagem_auditoria'

    # Identificação
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False,
                          default=datetime.utcnow, index=True)

    # Viagem relacionada
    viagem_id = db.Column(db.Integer, db.ForeignKey(
        'viagem.id'), nullable=False, index=True)

    # Usuário que executou a ação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_name = db.Column(db.String(100), nullable=True)
    user_role = db.Column(db.String(50), nullable=True)

    # Motorista envolvido (se aplicável)
    motorista_id = db.Column(db.Integer, db.ForeignKey(
        'motorista.id'), nullable=True, index=True)
    motorista_nome = db.Column(db.String(100), nullable=True)

    # Ação executada
    action = db.Column(db.String(50), nullable=False, index=True)
    # Ações possíveis:
    # - VIAGEM_CRIADA
    # - VIAGEM_ACEITA
    # - VIAGEM_INICIADA
    # - VIAGEM_FINALIZADA
    # - VIAGEM_CANCELADA (admin)
    # - MOTORISTA_DESASSOCIADO (motorista cancelou)
    # - STATUS_ALTERADO
    # - DADOS_ATUALIZADOS

    # Status antes e depois
    status_anterior = db.Column(db.String(20), nullable=True)
    status_novo = db.Column(db.String(20), nullable=True)

    # Detalhes da mudança
    changes = db.Column(db.Text, nullable=True)  # JSON com todas as mudanças
    # Motivo (especialmente para cancelamentos)
    reason = db.Column(db.Text, nullable=True)

    # Valores financeiros (para rastreamento)
    valor_repasse_anterior = db.Column(db.Numeric(10, 2), nullable=True)
    valor_repasse_novo = db.Column(db.Numeric(10, 2), nullable=True)

    # Contexto
    ip_address = db.Column(db.String(45), nullable=True)

    # Relacionamentos
    viagem = db.relationship('Viagem', backref='historico_auditoria')
    user = db.relationship('User', backref='viagens_auditadas')
    motorista = db.relationship('Motorista', backref='viagens_auditadas')

    def __repr__(self):
        return f'<ViagemAuditoria {self.id}: Viagem#{self.viagem_id} - {self.action} por {self.user_name}>'

    def to_dict(self):
        """Converte o registro para dicionário."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'viagem_id': self.viagem_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'user_role': self.user_role,
            'motorista_id': self.motorista_id,
            'motorista_nome': self.motorista_nome,
            'action': self.action,
            'status_anterior': self.status_anterior,
            'status_novo': self.status_novo,
            'changes': self.changes,
            'reason': self.reason,
            'valor_repasse_anterior': float(self.valor_repasse_anterior) if self.valor_repasse_anterior else None,
            'valor_repasse_novo': float(self.valor_repasse_novo) if self.valor_repasse_novo else None,
            'ip_address': self.ip_address
        }
