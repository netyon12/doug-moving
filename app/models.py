from . import db
from flask_login import UserMixin
from datetime import datetime


class Empresa(db.Model):
    __tablename__ = 'empresa'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    cnpj = db.Column(db.String(20), unique=True)
    endereco = db.Column(db.String(255))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    contato = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(10), nullable=False,
                       default='Ativo')  # Ativo ou Inativo

    # Relacionamentos: Uma empresa pode ter várias plantas, centros de custo e turnos
    plantas = db.relationship(
        'Planta', back_populates='empresa', cascade="all, delete-orphan")
    centros_custo = db.relationship(
        'CentroCusto', back_populates='empresa', cascade="all, delete-orphan")
    turnos = db.relationship(
        'Turno', back_populates='empresa', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Empresa {self.nome}>'


class Planta(db.Model):
    __tablename__ = 'planta'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)

    # Relacionamento: Uma planta pertence a uma empresa
    empresa = db.relationship('Empresa', back_populates='plantas')

    # Garante que o nome da planta seja único dentro da mesma empresa
    __table_args__ = (db.UniqueConstraint(
        'nome', 'empresa_id', name='_nome_empresa_uc'),)

    def __repr__(self):
        return f'<Planta {self.nome} - {self.empresa.nome}>'


class CentroCusto(db.Model):
    __tablename__ = 'centro_custo'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)

    # Relacionamento: Um centro de custo pertence a uma empresa
    empresa = db.relationship('Empresa', back_populates='centros_custo')

    # Garante que o código do centro de custo seja único dentro da mesma empresa
    __table_args__ = (db.UniqueConstraint(
        'codigo', 'empresa_id', name='_codigo_empresa_uc'),)

    def __repr__(self):
        return f'<CentroCusto {self.codigo} - {self.nome}>'


class Turno(db.Model):
    __tablename__ = 'turno'
    
    # Constantes para os nomes fixos de turno
    TURNO_1 = '1° Turno'
    TURNO_2 = '2° Turno'
    TURNO_3 = '3° Turno'
    TURNO_ADMIN = 'Administrativo'
    
    TURNOS_VALIDOS = [TURNO_1, TURNO_2, TURNO_3, TURNO_ADMIN]
    
    id = db.Column(db.Integer, primary_key=True)
    # Apenas valores permitidos: "1° Turno", "2° Turno", "3° Turno", "Administrativo"
    nome = db.Column(db.String(100), nullable=False)
    horario_inicio = db.Column(db.Time, nullable=False)
    horario_fim = db.Column(db.Time, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    # Associado a uma planta específica
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)

    # Relacionamentos
    empresa = db.relationship('Empresa', back_populates='turnos')
    planta = db.relationship('Planta')  # Relacionamento simples com Planta

    def __repr__(self):
        return f'<Turno {self.nome} ({self.horario_inicio}-{self.horario_fim})>'
    
    @staticmethod
    def validar_nome(nome):
        """Valida se o nome do turno está entre os valores permitidos."""
        return nome in Turno.TURNOS_VALIDOS
    
    def get_campo_valor_bloco(self):
        """Retorna o nome do campo de valor no modelo Bloco correspondente a este turno."""
        mapeamento = {
            self.TURNO_1: 'valor_turno1',
            self.TURNO_2: 'valor_turno2',
            self.TURNO_3: 'valor_turno3',
            self.TURNO_ADMIN: 'valor_admin'
        }
        return mapeamento.get(self.nome)
    
    def get_campo_repasse_bloco(self):
        """Retorna o nome do campo de repasse no modelo Bloco correspondente a este turno."""
        mapeamento = {
            self.TURNO_1: 'repasse_turno1',
            self.TURNO_2: 'repasse_turno2',
            self.TURNO_3: 'repasse_turno3',
            self.TURNO_ADMIN: 'repasse_admin'
        }
        return mapeamento.get(self.nome)


# =============================================================================
# NOVAS TABELAS (BLOCO, VALOR_BLOCO_TURNO, BAIRRO, GERENTE)
# =============================================================================

class Bloco(db.Model):
    __tablename__ = 'bloco'
    id = db.Column(db.Integer, primary_key=True)
    codigo_bloco = db.Column(db.String(50), nullable=False)
    nome_bloco = db.Column(db.String(150), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    status = db.Column(db.String(10), nullable=False,
                       default='Ativo')  # Ativo ou Inativo

    # Valores por turno (diretos no bloco)
    valor_turno1 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    repasse_turno1 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    valor_turno2 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    repasse_turno2 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    valor_turno3 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    repasse_turno3 = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    valor_admin = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    repasse_admin = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)

    empresa = db.relationship('Empresa')

    # Relacionamentos
    bairros = db.relationship('Bairro', back_populates='bloco', lazy='dynamic')
    colaboradores = db.relationship('Colaborador', back_populates='bloco')

    # Garante que o código do bloco seja único dentro da mesma empresa
    __table_args__ = (db.UniqueConstraint(
        'codigo_bloco', 'empresa_id', name='_codigo_bloco_empresa_uc'),)

    def __repr__(self):
        return f'<Bloco {self.codigo_bloco}>'
    
    def get_valor_por_turno(self, turno_obj):
        """
        Retorna o valor do bloco para um determinado turno.
        
        Args:
            turno_obj: Objeto Turno ou string com o nome do turno
            
        Returns:
            Decimal: Valor do bloco para o turno especificado
        """
        if isinstance(turno_obj, Turno):
            nome_turno = turno_obj.nome
        else:
            nome_turno = turno_obj
            
        mapeamento = {
            Turno.TURNO_1: self.valor_turno1,
            Turno.TURNO_2: self.valor_turno2,
            Turno.TURNO_3: self.valor_turno3,
            Turno.TURNO_ADMIN: self.valor_admin
        }
        return mapeamento.get(nome_turno, 0.00)
    
    def get_repasse_por_turno(self, turno_obj):
        """
        Retorna o valor de repasse do bloco para um determinado turno.
        
        Args:
            turno_obj: Objeto Turno ou string com o nome do turno
            
        Returns:
            Decimal: Valor de repasse para o turno especificado
        """
        if isinstance(turno_obj, Turno):
            nome_turno = turno_obj.nome
        else:
            nome_turno = turno_obj
            
        mapeamento = {
            Turno.TURNO_1: self.repasse_turno1,
            Turno.TURNO_2: self.repasse_turno2,
            Turno.TURNO_3: self.repasse_turno3,
            Turno.TURNO_ADMIN: self.repasse_admin
        }
        return mapeamento.get(nome_turno, 0.00)
    
    def set_valor_por_turno(self, turno_obj, valor):
        """
        Define o valor do bloco para um determinado turno.
        
        Args:
            turno_obj: Objeto Turno ou string com o nome do turno
            valor: Valor a ser definido
        """
        if isinstance(turno_obj, Turno):
            nome_turno = turno_obj.nome
        else:
            nome_turno = turno_obj
            
        if nome_turno == Turno.TURNO_1:
            self.valor_turno1 = valor
        elif nome_turno == Turno.TURNO_2:
            self.valor_turno2 = valor
        elif nome_turno == Turno.TURNO_3:
            self.valor_turno3 = valor
        elif nome_turno == Turno.TURNO_ADMIN:
            self.valor_admin = valor
    
    def set_repasse_por_turno(self, turno_obj, repasse):
        """
        Define o valor de repasse do bloco para um determinado turno.
        
        Args:
            turno_obj: Objeto Turno ou string com o nome do turno
            repasse: Valor de repasse a ser definido
        """
        if isinstance(turno_obj, Turno):
            nome_turno = turno_obj.nome
        else:
            nome_turno = turno_obj
            
        if nome_turno == Turno.TURNO_1:
            self.repasse_turno1 = repasse
        elif nome_turno == Turno.TURNO_2:
            self.repasse_turno2 = repasse
        elif nome_turno == Turno.TURNO_3:
            self.repasse_turno3 = repasse
        elif nome_turno == Turno.TURNO_ADMIN:
            self.repasse_admin = repasse


class Bairro(db.Model):
    __tablename__ = 'bairro'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cidade = db.Column(db.String(100), nullable=False)

    # A relação agora é que um Bairro pertence a um Bloco
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=True)
    bloco = db.relationship('Bloco', back_populates='bairros')

    # Garante que a combinação de nome e cidade seja única
    __table_args__ = (db.UniqueConstraint(
        'nome', 'cidade', name='_nome_cidade_uc'),)

    def __repr__(self):
        return f'<Bairro {self.nome}>'


# DEPRECATED: Tabela ValorBlocoTurno removida - valores agora estão diretos no Bloco
# class ValorBlocoTurno(db.Model):
#     """ Tabela associativa para armazenar o valor e repasse de um Bloco para um Turno específico. """
#     __tablename__ = 'valor_bloco_turno'
#     id = db.Column(db.Integer, primary_key=True)
#     bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=False)
#     turno_id = db.Column(db.Integer, db.ForeignKey('turno.id'), nullable=False)
#     valor = db.Column(db.Float, nullable=False, default=0.0)
#     valor_repasse = db.Column(db.Float, nullable=False, default=0.0)
#
#     bloco = db.relationship('Bloco', back_populates='valores_por_turno')
#     turno = db.relationship('Turno')
#
#     # Garante que só exista uma entrada de valor para cada par Bloco-Turno
#     __table_args__ = (db.UniqueConstraint(
#         'bloco_id', 'turno_id', name='_bloco_turno_uc'),)
#
#     def __repr__(self):
#         return f'<Valor Bloco {self.bloco.codigo_bloco} - Turno {self.turno.nome}: R${self.valor}>'


class Gerente(db.Model):
    __tablename__ = 'gerente'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)
    # Ativo, Inativo, Desligado, Ausente
    status = db.Column(db.String(20), nullable=False, default='Ativo')

    # Relacionamentos
    user = db.relationship('User', back_populates='gerente', uselist=False)
    empresa = db.relationship('Empresa')
    planta = db.relationship('Planta')

    # Relacionamento muitos-para-muitos com CentroCusto
    centros_custo = db.relationship(
        'CentroCusto', secondary='gerente_centro_custo_association')

    def __repr__(self):
        return f'<Gerente {self.nome}>'


# Tabela de associação para o relacionamento Muitos-para-Muitos entre Gerente e CentroCusto
gerente_centro_custo_association = db.Table('gerente_centro_custo_association',
                                            db.Column('gerente_id', db.Integer, db.ForeignKey(
                                                'gerente.id'), primary_key=True),
                                            db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                'centro_custo.id'), primary_key=True)
                                            )

# --- ATUALIZAÇÃO NO MODELO User ---
# Adicione este relacionamento dentro da classe User em app/models.py
# User.gerente = db.relationship('Gerente', back_populates='user', uselist=False)


# =============================================================================
# MODELOS ATUALIZADOS (SUPERVISOR, COLABORADOR, MOTORISTA)
# =============================================================================

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
    planta = db.relationship('Planta', foreign_keys=[planta_id])  # Relacionamento antigo (compatibilidade)
    gerente = db.relationship('Gerente')

    # Relacionamentos Muitos-para-Muitos
    plantas = db.relationship('Planta', secondary='supervisor_planta_association')  # NOVO: Múltiplas plantas
    turnos = db.relationship('Turno', secondary='supervisor_turno_association')
    centros_custo = db.relationship(
        'CentroCusto', secondary='supervisor_centro_custo_association')


class Colaborador(db.Model):
    __tablename__ = 'colaborador'
    id = db.Column(db.Integer, primary_key=True)
    # ID do Colaborador (matrícula)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    # Email pode ser nulo, mas se preenchido deve ser único
    # Removemos unique=True para evitar erro com múltiplos valores vazios
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

    # Mantemos o campo de texto para o nome do bairro
    bairro = db.Column(db.String(100))
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=True)
    bloco = db.relationship('Bloco')


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

    # Relacionamentos
    user = db.relationship('User', back_populates='motorista', uselist=False)
    viagens = db.relationship('Viagem', back_populates='motorista')
    
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

# --- TABELAS DE ASSOCIAÇÃO PARA RELACIONAMENTOS M-M ---


supervisor_turno_association = db.Table('supervisor_turno_association',
                                        db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                            'supervisor.id'), primary_key=True),
                                        db.Column('turno_id', db.Integer, db.ForeignKey(
                                            'turno.id'), primary_key=True)
                                        )

supervisor_centro_custo_association = db.Table('supervisor_centro_custo_association',
                                               db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                                   'supervisor.id'), primary_key=True),
                                               db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                   'centro_custo.id'), primary_key=True)
                                               )

supervisor_planta_association = db.Table('supervisor_planta_association',
                                         db.Column('supervisor_id', db.Integer, db.ForeignKey(
                                             'supervisor.id'), primary_key=True),
                                         db.Column('planta_id', db.Integer, db.ForeignKey(
                                             'planta.id'), primary_key=True)
                                         )

colaborador_turno_association = db.Table('colaborador_turno_association',
                                         db.Column('colaborador_id', db.Integer, db.ForeignKey(
                                             'colaborador.id'), primary_key=True),
                                         db.Column('turno_id', db.Integer, db.ForeignKey(
                                             'turno.id'), primary_key=True)
                                         )

colaborador_centro_custo_association = db.Table('colaborador_centro_custo_association',
                                                db.Column('colaborador_id', db.Integer, db.ForeignKey(
                                                    'colaborador.id'), primary_key=True),
                                                db.Column('centro_custo_id', db.Integer, db.ForeignKey(
                                                    'centro_custo.id'), primary_key=True)
                                                )

# --- ATUALIZAÇÃO FINAL NO MODELO User ---
# Garanta que sua classe User tenha os relacionamentos para os novos perfis.
# User.gerente = db.relationship('Gerente', back_populates='user', uselist=False)
# E mantenha os já existentes para Supervisor e Motorista.

# ===========================================================================================


class User(UserMixin, db.Model):
    __tablename__ = 'user'  # É uma boa prática nomear a tabela explicitamente
    id = db.Column(db.Integer, primary_key=True)
    # 'email' é o login/usuário
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # 'admin', 'gerente', 'supervisor', 'motorista'
    role = db.Column(db.String(20), nullable=False)
    foto_perfil = db.Column(
        db.String(100), nullable=False, default='default.jpg')

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


# =============================================================================
# MODELO DE CONFIGURAÇÕES GLOBAIS
# =============================================================================

class Configuracao(db.Model):
    """Armazena configurações globais do sistema como pares de chave-valor."""
    __tablename__ = 'configuracao'
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Configuracao {self.chave}={self.valor}>'


# =============================================================================
# MODELOS DE OPERAÇÃO (VIAGEM E SOLICITACAO)
# =============================================================================

class Viagem(db.Model):
    """
    Modelo de Viagem com estrutura completa para gerenciamento de transporte.
    
    Status possíveis:
    - 'Pendente': Viagem criada após agrupamento, aguardando motorista aceitar
    - 'Agendada': Motorista aceitou a viagem
    - 'Em Andamento': Motorista iniciou a viagem
    - 'Finalizada': Viagem concluída com sucesso
    - 'Cancelada': Viagem cancelada por Admin/Supervisor/Motorista
    """
    __tablename__ = 'viagem'
    
    # === IDENTIFICAÇÃO ===
    id = db.Column(db.Integer, primary_key=True)
    
    # === LOCALIZAÇÃO E CONTEXTO ===
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey('planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=True)  # Bloco principal
    blocos_ids = db.Column(db.String(255), nullable=True)  # "1,3,5" para múltiplos blocos
    
    # === TIPO DE VIAGEM ===
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    tipo_corrida = db.Column(db.String(20), nullable=False)  # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    
    # === HORÁRIOS ===
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)
    
    # === PASSAGEIROS ===
    colaboradores_ids = db.Column(db.Text, nullable=True)  # JSON: "[1, 5, 8, 12]"
    quantidade_passageiros = db.Column(db.Integer, default=0)  # Calculado automaticamente
    
    # === MOTORISTA E VEÍCULO ===
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=True)
    nome_motorista = db.Column(db.String(150), nullable=True)  # Preenchido quando motorista aceitar
    placa_veiculo = db.Column(db.String(20), nullable=True)  # Preenchido quando motorista aceitar
    
    # === VALORES FINANCEIROS ===
    valor = db.Column(db.Numeric(10, 2), nullable=True)  # Valor total da viagem (MAIOR valor entre solicitações)
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=True)  # Valor de repasse para o motorista
    
    # === STATUS E CONTROLE ===
    status = db.Column(db.String(20), nullable=False, default='Pendente')
    motivo_cancelamento = db.Column(db.Text, nullable=True)  # Preenchido se cancelada
    cancelado_por_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Quem cancelou
    
    # === AUDITORIA E TIMESTAMPS ===
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Quem criou (admin/supervisor)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_inicio = db.Column(db.DateTime, nullable=True)  # Quando motorista iniciou
    data_finalizacao = db.Column(db.DateTime, nullable=True)  # Quando motorista finalizou
    data_cancelamento = db.Column(db.DateTime, nullable=True)  # Quando foi cancelada
    
    # === RELACIONAMENTOS ===
    empresa = db.relationship('Empresa', backref='viagens')
    planta = db.relationship('Planta', backref='viagens')
    bloco = db.relationship('Bloco', backref='viagens')
    motorista = db.relationship('Motorista', back_populates='viagens')
    solicitacoes = db.relationship('Solicitacao', back_populates='viagem', cascade="all, delete-orphan")
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='viagens_criadas')
    cancelado_por = db.relationship('User', foreign_keys=[cancelado_por_user_id], backref='viagens_canceladas')

    def __repr__(self):
        motorista_info = self.nome_motorista if self.nome_motorista else "Não atribuído"
        return f'<Viagem {self.id} - {motorista_info} - Status: {self.status}>'
    
    # === MÉTODOS AUXILIARES ===
    
    def pode_ser_aceita(self):
        """Verifica se a viagem pode ser aceita por um motorista."""
        return self.status == 'Pendente' and self.motorista_id is None
    
    def pode_ser_iniciada(self, motorista_id):
        """Verifica se a viagem pode ser iniciada pelo motorista especificado."""
        return self.status == 'Agendada' and self.motorista_id == motorista_id
    
    def pode_ser_finalizada(self, motorista_id):
        """Verifica se a viagem pode ser finalizada pelo motorista especificado."""
        return self.status == 'Em Andamento' and self.motorista_id == motorista_id
    
    def pode_ser_cancelada(self):
        """Verifica se a viagem pode ser cancelada."""
        return self.status in ['Pendente', 'Agendada']
    
    def aceitar_viagem(self, motorista):
        """
        Aceita a viagem para um motorista específico.
        
        Args:
            motorista: Objeto Motorista que está aceitando a viagem
            
        Returns:
            bool: True se aceito com sucesso, False caso contrário
        """
        if not self.pode_ser_aceita():
            return False
        
        self.motorista_id = motorista.id
        self.nome_motorista = motorista.nome
        self.placa_veiculo = motorista.veiculo_placa
        self.status = 'Agendada'
        self.data_atualizacao = datetime.utcnow()
        
        # Atualiza status das solicitações
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Agendada'
        
        return True
    
    def iniciar_viagem(self, motorista_id):
        """
        Inicia a viagem.
        
        Args:
            motorista_id: ID do motorista que está iniciando
            
        Returns:
            bool: True se iniciado com sucesso, False caso contrário
        """
        if not self.pode_ser_iniciada(motorista_id):
            return False
        
        self.status = 'Em Andamento'
        self.data_inicio = datetime.utcnow()
        self.data_atualizacao = datetime.utcnow()
        
        # Atualiza status das solicitações
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Em Andamento'
        
        return True
    
    def finalizar_viagem(self, motorista_id):
        """
        Finaliza a viagem.
        
        Args:
            motorista_id: ID do motorista que está finalizando
            
        Returns:
            bool: True se finalizado com sucesso, False caso contrário
        """
        if not self.pode_ser_finalizada(motorista_id):
            return False
        
        self.status = 'Finalizada'
        self.data_finalizacao = datetime.utcnow()
        self.data_atualizacao = datetime.utcnow()
        
        # Atualiza status das solicitações
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Finalizada'
        
        return True
    
    def cancelar_viagem(self, motivo, user_id):
        """
        Cancela a viagem e reverte as solicitações para Pendente.
        
        Args:
            motivo: Motivo do cancelamento
            user_id: ID do usuário que está cancelando
            
        Returns:
            bool: True se cancelado com sucesso, False caso contrário
        """
        if not self.pode_ser_cancelada():
            return False
        
        self.status = 'Cancelada'
        self.motivo_cancelamento = motivo
        self.cancelado_por_user_id = user_id
        self.data_cancelamento = datetime.utcnow()
        self.data_atualizacao = datetime.utcnow()
        
        # Reverte solicitações para Pendente
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Pendente'
            solicitacao.viagem_id = None
        
        return True
    
    def get_colaboradores_lista(self):
        """
        Retorna lista de IDs dos colaboradores a partir do campo JSON.
        
        Returns:
            list: Lista de IDs de colaboradores
        """
        if not self.colaboradores_ids:
            return []
        
        try:
            import json
            return json.loads(self.colaboradores_ids)
        except:
            # Se não for JSON válido, tenta split por vírgula
            return [int(x.strip()) for x in self.colaboradores_ids.split(',') if x.strip().isdigit()]
    
    def get_blocos_lista(self):
        """
        Retorna lista de IDs dos blocos a partir do campo string.
        
        Returns:
            list: Lista de IDs de blocos
        """
        if not self.blocos_ids:
            return [self.bloco_id] if self.bloco_id else []
        
        try:
            return [int(x.strip()) for x in self.blocos_ids.split(',') if x.strip().isdigit()]
        except:
            return [self.bloco_id] if self.bloco_id else []
        

    def desassociar_motorista(self):
        """
        Desassocia o motorista da viagem, tornando-a disponível novamente.
        Usado quando o motorista cancela antes de iniciar a viagem.
        
        Returns:
            bool: True se desassociado com sucesso, False caso contrário
        """
        # Só pode desassociar se estiver Agendada (motorista aceitou mas não iniciou)
        if self.status != 'Agendada':
            return False
        
        # Remove associação com motorista
        self.motorista_id = None
        self.nome_motorista = None
        self.placa_veiculo = None
        
        # Volta status para Pendente
        self.status = 'Pendente'
        self.data_atualizacao = datetime.utcnow()
        
        # Reverte status das solicitações para Pendente
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Pendente'
        
        return True







class Solicitacao(db.Model):
    __tablename__ = 'solicitacao'
    id = db.Column(db.Integer, primary_key=True)
    
    # Relacionamentos principais
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaborador.id'), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey('planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=False)
    
    # Tipo de linha e corrida
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    tipo_corrida = db.Column(db.String(20), nullable=False)  # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    
    # Horários
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)
    
    # Turnos (referências aos turnos calculados)
    turno_entrada_id = db.Column(db.Integer, db.ForeignKey('turno.id'), nullable=True)
    turno_saida_id = db.Column(db.Integer, db.ForeignKey('turno.id'), nullable=True)
    turno_desligamento_id = db.Column(db.Integer, db.ForeignKey('turno.id'), nullable=True)
    
    # Status e viagem/fretado
    status = db.Column(db.String(20), nullable=False, default='Pendente')  # Pendente, Agrupada, Fretado, Finalizada, Cancelada
    viagem_id = db.Column(db.Integer, db.ForeignKey('viagem.id'), nullable=True)  # NULL até agrupar
    fretado_id = db.Column(db.Integer, db.ForeignKey('fretado.id'), nullable=True)  # NULL até agrupar como fretado
    
    # Valores financeiros
    valor = db.Column(db.Numeric(10, 2), nullable=True)  # Valor baseado em ValorBlocoTurno
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=True)  # Valor de repasse para o motorista
    
    # Rastreamento de quem criou
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Usuário que criou a solicitação
    
    # Timestamps
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    colaborador = db.relationship('Colaborador', backref='solicitacoes')
    supervisor = db.relationship('Supervisor', backref='solicitacoes')
    empresa = db.relationship('Empresa', backref='solicitacoes')
    planta = db.relationship('Planta', backref='solicitacoes')
    bloco = db.relationship('Bloco', backref='solicitacoes')
    turno_entrada = db.relationship('Turno', foreign_keys=[turno_entrada_id])
    turno_saida = db.relationship('Turno', foreign_keys=[turno_saida_id])
    turno_desligamento = db.relationship('Turno', foreign_keys=[turno_desligamento_id])
    viagem = db.relationship('Viagem', back_populates='solicitacoes')
    fretado = db.relationship('Fretado', backref='solicitacoes', foreign_keys='Solicitacao.fretado_id')
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='solicitacoes_criadas')

    def __repr__(self):
        return f'<Solicitacao {self.id} - {self.colaborador.nome} - {self.tipo_corrida}>'
    

    

# ===========================================================================================
# TABELAS DE AUDITORIA E LOGS
# ===========================================================================================

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
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Usuário que executou a ação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    user_name = db.Column(db.String(100), nullable=True)  # Desnormalizado para histórico
    user_role = db.Column(db.String(50), nullable=True)  # admin, motorista, supervisor, etc.
    
    # Ação executada
    action = db.Column(db.String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, etc.
    resource_type = db.Column(db.String(50), nullable=False, index=True)  # Viagem, User, Motorista, etc.
    resource_id = db.Column(db.Integer, nullable=True, index=True)  # ID do recurso afetado
    
    # Status da operação
    status = db.Column(db.String(20), nullable=False, default='SUCCESS')  # SUCCESS, FAILED, ERROR
    
    # Contexto da requisição
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 ou IPv6
    user_agent = db.Column(db.String(255), nullable=True)  # Navegador/dispositivo
    request_method = db.Column(db.String(10), nullable=True)  # GET, POST, PUT, DELETE
    route = db.Column(db.String(255), nullable=True)  # Rota/endpoint acessado
    module = db.Column(db.String(50), nullable=True)  # Blueprint/módulo
    
    # Detalhes da mudança
    changes = db.Column(db.Text, nullable=True)  # JSON com before/after
    reason = db.Column(db.Text, nullable=True)  # Motivo da ação (quando aplicável)
    error_message = db.Column(db.Text, nullable=True)  # Mensagem de erro (se falhou)
    
    # Metadados adicionais
    session_id = db.Column(db.String(100), nullable=True)  # ID da sessão
    duration_ms = db.Column(db.Integer, nullable=True)  # Tempo de execução em ms
    severity = db.Column(db.String(20), nullable=False, default='INFO')  # INFO, WARNING, ERROR, CRITICAL
    
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
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Viagem relacionada
    viagem_id = db.Column(db.Integer, db.ForeignKey('viagem.id'), nullable=False, index=True)
    
    # Usuário que executou a ação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user_name = db.Column(db.String(100), nullable=True)
    user_role = db.Column(db.String(50), nullable=True)
    
    # Motorista envolvido (se aplicável)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=True, index=True)
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
    reason = db.Column(db.Text, nullable=True)  # Motivo (especialmente para cancelamentos)
    
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


# ===========================================================================================
# FIM DAS TABELAS DE AUDITORIA
# ===========================================================================================




# ===========================================================================================
# MÓDULO FINANCEIRO
# ===========================================================================================

class FinContasReceber(db.Model):
    """Modelo para Contas a Receber (Títulos das Empresas)"""
    __tablename__ = 'fin_contas_receber'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_titulo = db.Column(db.String(50), unique=True, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='Aberto')  # Aberto, Recebido, Vencido, Cancelado
    numero_nota_fiscal = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    empresa = db.relationship('Empresa', backref='titulos_receber')
    created_by = db.relationship('User', backref='titulos_receber_criados')
    viagens = db.relationship('FinReceberViagens', back_populates='conta_receber', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<FinContasReceber {self.numero_titulo} - {self.empresa.nome if self.empresa else "N/A"}>'


class FinReceberViagens(db.Model):
    """Modelo para vincular viagens aos títulos a receber"""
    __tablename__ = 'fin_receber_viagens'
    
    id = db.Column(db.Integer, primary_key=True)
    conta_receber_id = db.Column(db.Integer, db.ForeignKey('fin_contas_receber.id', ondelete='CASCADE'), nullable=False)
    viagem_id = db.Column(db.Integer, db.ForeignKey('viagem.id'), nullable=False)
    valor_viagem = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    conta_receber = db.relationship('FinContasReceber', back_populates='viagens')
    viagem = db.relationship('Viagem', backref='titulo_receber')
    
    # Constraint única para evitar duplicação
    __table_args__ = (db.UniqueConstraint('conta_receber_id', 'viagem_id', name='_conta_viagem_receber_uc'),)
    
    def __repr__(self):
        return f'<FinReceberViagens Título:{self.conta_receber_id} Viagem:{self.viagem_id}>'


class FinContasPagar(db.Model):
    """Modelo para Contas a Pagar (Títulos dos Motoristas)"""
    __tablename__ = 'fin_contas_pagar'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_titulo = db.Column(db.String(50), unique=True, nullable=False)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='Aberto')  # Aberto, Pago, Vencido, Cancelado
    forma_pagamento = db.Column(db.String(50))  # PIX, Transferência, Dinheiro, etc.
    comprovante_pagamento = db.Column(db.String(255))  # Caminho do arquivo
    observacoes = db.Column(db.Text)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    motorista = db.relationship('Motorista', backref='titulos_pagar')
    created_by = db.relationship('User', backref='titulos_pagar_criados')
    viagens = db.relationship('FinPagarViagens', back_populates='conta_pagar', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<FinContasPagar {self.numero_titulo} - {self.motorista.nome if self.motorista else "N/A"}>'


class FinPagarViagens(db.Model):
    """Modelo para vincular viagens aos títulos a pagar"""
    __tablename__ = 'fin_pagar_viagens'
    
    id = db.Column(db.Integer, primary_key=True)
    conta_pagar_id = db.Column(db.Integer, db.ForeignKey('fin_contas_pagar.id', ondelete='CASCADE'), nullable=False)
    viagem_id = db.Column(db.Integer, db.ForeignKey('viagem.id'), nullable=False)
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    conta_pagar = db.relationship('FinContasPagar', back_populates='viagens')
    viagem = db.relationship('Viagem', backref='titulo_pagar')
    
    # Constraint única para evitar duplicação
    __table_args__ = (db.UniqueConstraint('conta_pagar_id', 'viagem_id', name='_conta_viagem_pagar_uc'),)
    
    def __repr__(self):
        return f'<FinPagarViagens Título:{self.conta_pagar_id} Viagem:{self.viagem_id}>'

# ===========================================================================================
# FIM DO MÓDULO FINANCEIRO
# ===========================================================================================




# ===========================================================================================
# MODELO DE FRETADO
# ===========================================================================================

class Fretado(db.Model):
    """
    Modelo de Fretado para gerenciar registros individuais de colaboradores em fretados.
    
    Cada colaborador que vai de fretado gera 1 registro nesta tabela.
    Similar à estrutura da tabela Solicitacao, mas para fretados.
    """
    __tablename__ = 'fretado'
    
    # === IDENTIFICAÇÃO ===
    id = db.Column(db.Integer, primary_key=True)
    
    # === REFERÊNCIAS ===
    solicitacao_id = db.Column(db.Integer, db.ForeignKey('solicitacao.id'), nullable=False)  # ID da solicitação original
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaborador.id'), nullable=False)  # ID do colaborador
    
    # === DADOS DO COLABORADOR ===
    nome_colaborador = db.Column(db.String(150), nullable=False)  # Nome do colaborador
    matricula = db.Column(db.String(50), nullable=True)  # Matrícula do colaborador
    telefone = db.Column(db.String(20), nullable=True)  # Telefone do colaborador
    
    # === ENDEREÇO DO COLABORADOR ===
    endereco = db.Column(db.String(255), nullable=True)  # Endereço completo
    bairro = db.Column(db.String(100), nullable=True)  # Bairro
    cidade = db.Column(db.String(100), nullable=True)  # Cidade
    
    # === LOCALIZAÇÃO E CONTEXTO ===
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey('planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=True)  # Bloco do colaborador
    grupo_bloco = db.Column(db.String(50), nullable=True)  # Ex: "CPV1", "SJC1" - raiz do código do bloco
    
    # === TIPO DE VIAGEM ===
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    tipo_corrida = db.Column(db.String(20), nullable=False)  # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    
    # === HORÁRIOS ===
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)
    
    # === STATUS E CONTROLE ===
    status = db.Column(db.String(20), nullable=False, default='Fretado')  # Status: 'Fretado'
    observacoes = db.Column(db.Text, nullable=True)  # Observações gerais
    
    # === AUDITORIA E TIMESTAMPS ===
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Quem criou
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # === RELACIONAMENTOS ===
    solicitacao = db.relationship('Solicitacao', foreign_keys=[solicitacao_id])
    colaborador = db.relationship('Colaborador', foreign_keys=[colaborador_id])
    empresa = db.relationship('Empresa', foreign_keys=[empresa_id])
    planta = db.relationship('Planta', foreign_keys=[planta_id])
    bloco = db.relationship('Bloco', foreign_keys=[bloco_id])
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='fretados_criados')

    def __repr__(self):
        return f'<Fretado {self.id} - {self.nome_colaborador} - {self.grupo_bloco}>'
    
    # === MÉTODOS AUXILIARES ===
    
    def get_colaboradores_lista(self):
        """
        Retorna lista de IDs dos colaboradores a partir do campo JSON.
        
        Returns:
            list: Lista de IDs de colaboradores
        """
        if not self.colaboradores_ids:
            return []
        
        try:
            import json
            return json.loads(self.colaboradores_ids)
        except:
            # Se não for JSON válido, tenta split por vírgula
            return [int(x.strip()) for x in self.colaboradores_ids.split(',') if x.strip().isdigit()]
    
    def get_blocos_lista(self):
        """
        Retorna lista de IDs dos blocos a partir do campo string.
        
        Returns:
            list: Lista de IDs de blocos
        """
        if not self.blocos_ids:
            return [self.bloco_id] if self.bloco_id else []
        
        try:
            return [int(x.strip()) for x in self.blocos_ids.split(',') if x.strip().isdigit()]
        except:
            return [self.bloco_id] if self.bloco_id else []
    
    @staticmethod
    def extrair_grupo_bloco(codigo_bloco):
        """
        Extrai o grupo de bloco a partir do código do bloco.
        
        Exemplos:
            CPV1.1 → CPV1
            CPV1.2 → CPV1
            SJC1.3 → SJC1
            ABC → ABC (sem ponto, retorna o próprio código)
        
        Args:
            codigo_bloco: String com o código do bloco
            
        Returns:
            str: Grupo do bloco (raiz antes do último ponto)
        """
        if not codigo_bloco:
            return None
        
        # Se tem ponto, pega tudo antes do último ponto
        if '.' in codigo_bloco:
            return codigo_bloco.rsplit('.', 1)[0]
        
        # Se não tem ponto, retorna o próprio código
        return codigo_bloco
    
    def to_dict(self):
        """Converte o fretado para dicionário."""
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'empresa_nome': self.empresa.nome if self.empresa else None,
            'planta_id': self.planta_id,
            'planta_nome': self.planta.nome if self.planta else None,
            'bloco_id': self.bloco_id,
            'bloco_codigo': self.bloco.codigo_bloco if self.bloco else None,
            'blocos_ids': self.blocos_ids,
            'grupo_bloco': self.grupo_bloco,
            'tipo_linha': self.tipo_linha,
            'tipo_corrida': self.tipo_corrida,
            'horario_entrada': self.horario_entrada.isoformat() if self.horario_entrada else None,
            'horario_saida': self.horario_saida.isoformat() if self.horario_saida else None,
            'horario_desligamento': self.horario_desligamento.isoformat() if self.horario_desligamento else None,
            'colaboradores_ids': self.colaboradores_ids,
            'quantidade_passageiros': self.quantidade_passageiros,
            'valor': float(self.valor) if self.valor else 0.00,
            'valor_repasse': float(self.valor_repasse) if self.valor_repasse else 0.00,
            'status': self.status,
            'observacoes': self.observacoes,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
        }

# ===========================================================================================
# FIM DO MODELO DE FRETADO
# ===========================================================================================

