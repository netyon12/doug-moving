"""
Modelos de Cadastros de Pessoas
===============================

Classes relacionadas a perfis de usuários do sistema:
- Gerente: Gerentes responsáveis por plantas
- Supervisor: Supervisores de colaboradores
- Colaborador: Colaboradores que solicitam transporte
- Motorista: Motoristas que executam viagens

Inclui também as tabelas de associação para relacionamentos N:N
"""

from app import db
from datetime import datetime


class Gerente(db.Model):
    __tablename__ = 'gerente'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)

    # Ativo, Inativo, Desligado, Ausente
    status = db.Column(db.String(20), nullable=False, default='Ativo')

    # Relacionamentos
    user = db.relationship('User', back_populates='gerente', uselist=False)
    empresa = db.relationship('Empresa')

    # Relacionamento N:N com Planta
    plantas = db.relationship(
        'Planta',
        secondary='gerente_planta_association',
        backref=db.backref('gerentes', lazy='dynamic'),
        lazy='dynamic'
    )

    # Relacionamento muitos-para-muitos com CentroCusto
    centros_custo = db.relationship(
        'CentroCusto', secondary='gerente_centro_custo_association')

    def __repr__(self):
        return f'<Gerente {self.nome}>'

    def get_plantas_ids(self):
        """Retorna lista de IDs das plantas associadas ao gerente"""
        return [p.id for p in self.plantas.all()]

    def get_empresa_plantas(self):
        """Retorna apenas plantas da empresa do gerente"""
        return self.plantas.filter_by(empresa_id=self.empresa_id).all()


class Supervisor(db.Model):
    __tablename__ = 'supervisor'
    id = db.Column(db.Integer, primary_key=True)  # ID sequencial interno
    # ID do Supervisor (matrícula)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    # Ativo, Desligado, Ausente, Inativo
    status = db.Column(db.String(20), nullable=False, default='Ativo')

    # Chaves estrangeiras para a hierarquia
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=True)  # Mantido para compatibilidade, será depreciado
    gerente_id = db.Column(db.Integer, db.ForeignKey(
        'gerente.id'), nullable=False)  # Gerente responsável

    # Relacionamentos
    user = db.relationship('User', back_populates='supervisor', uselist=False)
    empresa = db.relationship('Empresa')
    # Relacionamento antigo (compatibilidade)
    planta = db.relationship('Planta', foreign_keys=[
                             planta_id], overlaps="plantas")
    gerente = db.relationship('Gerente')

    # Relacionamentos Muitos-para-Muitos
    plantas = db.relationship('Planta', secondary='supervisor_planta_association',
                              overlaps="planta")  # NOVO: Múltiplas plantas
    turnos = db.relationship('Turno', secondary='supervisor_turno_association')
    centros_custo = db.relationship(
        'CentroCusto', secondary='supervisor_centro_custo_association')

    def __repr__(self):
        return f'<Supervisor {self.nome}>'


class Colaborador(db.Model):
    __tablename__ = 'colaborador'

    # Constantes de status
    STATUS_ATIVO = 'Ativo'
    STATUS_INATIVO = 'Inativo'
    STATUS_DESLIGADO = 'Desligado'
    STATUS_AUSENTE = 'Ausente'

    STATUS_VALIDOS = [STATUS_ATIVO, STATUS_INATIVO,
                      STATUS_DESLIGADO, STATUS_AUSENTE]

    id = db.Column(db.Integer, primary_key=True)
    # ID do Colaborador (matrícula)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    # Email pode ser nulo, mas se preenchido deve ser único
    email = db.Column(db.String(120), nullable=True)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    # Ativo, Inativo, Desligado, Ausente
    status = db.Column(db.String(20), nullable=False, default='Ativo')

    # Chaves estrangeiras
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)

    # Relacionamentos
    empresa = db.relationship('Empresa')
    planta = db.relationship('Planta')

    # Relacionamentos Muitos-para-Muitos
    turnos = db.relationship(
        'Turno', secondary='colaborador_turno_association')
    centros_custo = db.relationship(
        'CentroCusto', secondary='colaborador_centro_custo_association')

    # Bloco associado
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=True)
    bloco = db.relationship('Bloco', back_populates='colaboradores')

    def __repr__(self):
        return f'<Colaborador {self.nome}>'


class Motorista(db.Model):
    __tablename__ = 'motorista'
    id = db.Column(db.Integer, primary_key=True)  # ID sequencial do motorista
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    cpf_cnpj = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    chave_pix = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False,
                       default='Ativo')  # Ativo ou Inativo
    status_disponibilidade = db.Column(db.String(20), nullable=False,
                                       default='online')  # online ou offline
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    # Informações do Veículo
    veiculo_nome = db.Column(db.String(100))
    veiculo_placa = db.Column(db.String(10), unique=True)
    veiculo_cor = db.Column(db.String(50))
    veiculo_ano = db.Column(db.Integer)
    veiculo_km = db.Column(db.Float)
    veiculo_obs = db.Column(db.Text)

    # =========================================================================
    # CAMPOS MULTI-TENANT - Controle de acesso a múltiplas empresas
    # =========================================================================
    # Lista de slugs das empresas que o motorista tem acesso (ex: 'lear,nsg')
    empresas_acesso = db.Column(db.Text)
    # Empresa padrão ao logar (slug)
    empresa_padrao_slug = db.Column(db.String(50))

    # Relacionamentos
    user = db.relationship('User', back_populates='motorista', uselist=False)
    viagens = db.relationship('Viagem', back_populates='motorista')

    def __repr__(self):
        return f'<Motorista {self.nome}>'

    def get_status_atual(self):
        """
        Retorna o status atual do motorista baseado em suas viagens.

        Returns:
            str: 'offline', 'disponivel', 'agendado', 'ocupado'
        """
        # Se motorista está offline manualmente
        if self.status_disponibilidade == 'offline':
            return 'offline'

        # Verifica se tem viagem em andamento
        from app.models import Viagem
        viagem_em_andamento = Viagem.query.filter_by(
            motorista_id=self.id,
            status='Em Andamento'
        ).first()
        if viagem_em_andamento:
            return 'ocupado'

        # Verifica se tem viagem agendada
        viagem_agendada = Viagem.query.filter_by(
            motorista_id=self.id,
            status='Agendada'
        ).first()
        if viagem_agendada:
            return 'agendado'

        # Se não tem viagens e está online
        return 'disponivel'

    def get_status_badge(self):
        """
        Retorna a classe CSS e texto para o badge de status.

        Returns:
            dict: {'classe': 'bg-success', 'texto': 'Disponível', 'icone': 'check-circle'}
        """
        status = self.get_status_atual()

        badges = {
            'disponivel': {
                'classe': 'bg-success',
                'texto': 'Disponível',
                'icone': 'check-circle'
            },
            'agendado': {
                'classe': 'bg-primary',
                'texto': 'Agendado',
                'icone': 'calendar-check'
            },
            'ocupado': {
                'classe': 'bg-warning text-dark',
                'texto': 'Ocupado',
                'icone': 'hourglass-split'
            },
            'offline': {
                'classe': 'bg-secondary',
                'texto': 'Offline',
                'icone': 'power'
            }
        }

        return badges.get(status, badges['disponivel'])

    # =========================================================================
    # MÉTODOS MULTI-TENANT
    # =========================================================================
    def get_empresas_lista(self):
        """
        Retorna lista de slugs das empresas que o motorista tem acesso.
        
        Returns:
            list: Lista de slugs (ex: ['lear', 'nsg'])
        """
        if self.empresas_acesso:
            return [e.strip().lower() for e in self.empresas_acesso.split(',') if e.strip()]
        return []
    
    def tem_acesso_empresa(self, slug):
        """
        Verifica se o motorista tem acesso a determinada empresa.
        
        Args:
            slug: Slug da empresa (ex: 'lear', 'nsg')
            
        Returns:
            bool: True se tem acesso, False caso contrário
        """
        if not slug:
            return False
        return slug.lower() in self.get_empresas_lista()
    
    def adicionar_empresa_acesso(self, slug):
        """
        Adiciona uma empresa à lista de acesso do motorista.
        
        Args:
            slug: Slug da empresa a adicionar
        """
        empresas = self.get_empresas_lista()
        if slug.lower() not in empresas:
            empresas.append(slug.lower())
            self.empresas_acesso = ','.join(empresas)
    
    def remover_empresa_acesso(self, slug):
        """
        Remove uma empresa da lista de acesso do motorista.
        
        Args:
            slug: Slug da empresa a remover
        """
        empresas = self.get_empresas_lista()
        if slug.lower() in empresas:
            empresas.remove(slug.lower())
            self.empresas_acesso = ','.join(empresas) if empresas else None


# =============================================================================
# TABELAS DE ASSOCIAÇÃO PARA RELACIONAMENTOS MUITOS-PARA-MUITOS
# =============================================================================

# Gerente <-> Planta
gerente_planta_association = db.Table('gerente_planta_association',
                                      db.Column('gerente_id', db.Integer, db.ForeignKey(
                                          'gerente.id'), primary_key=True),
                                      db.Column('planta_id', db.Integer, db.ForeignKey(
                                          'planta.id'), primary_key=True)
                                      )

# Gerente <-> CentroCusto
gerente_centro_custo_association = db.Table('gerente_centro_custo_association',
                                            db.Column('gerente_id', db.Integer, db.ForeignKey(
                                                'gerente.id'), primary_key=True),
                                            db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                'centro_custo.id'), primary_key=True)
                                            )

# Supervisor <-> Turno
supervisor_turno_association = db.Table('supervisor_turno_association',
                                        db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                            'supervisor.id'), primary_key=True),
                                        db.Column('turno_id', db.Integer, db.ForeignKey(
                                            'turno.id'), primary_key=True)
                                        )

# Supervisor <-> CentroCusto
supervisor_centro_custo_association = db.Table('supervisor_centro_custo_association',
                                               db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                                   'supervisor.id'), primary_key=True),
                                               db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                   'centro_custo.id'), primary_key=True)
                                               )

# Supervisor <-> Planta
supervisor_planta_association = db.Table('supervisor_planta_association',
                                         db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                             'supervisor.id'), primary_key=True),
                                         db.Column('planta_id', db.Integer, db.ForeignKey(
                                             'planta.id'), primary_key=True)
                                         )

# Colaborador <-> Turno
colaborador_turno_association = db.Table('colaborador_turno_association',
                                         db.Column('colaborador_id', db.Integer, db.ForeignKey(
                                             'colaborador.id'), primary_key=True),
                                         db.Column('turno_id', db.Integer, db.ForeignKey(
                                             'turno.id'), primary_key=True)
                                         )

# Colaborador <-> CentroCusto
colaborador_centro_custo_association = db.Table('colaborador_centro_custo_association',
                                                db.Column('colaborador_id', db.Integer, db.ForeignKey(
                                                    'colaborador.id'), primary_key=True),
                                                db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                    'centro_custo.id'), primary_key=True)
                                                )
