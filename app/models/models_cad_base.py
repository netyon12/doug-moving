"""
Modelos de Cadastros Base
=========================

Classes relacionadas a entidades cadastrais base do sistema:
- Empresa: Empresas clientes
- Planta: Plantas/unidades das empresas
- CentroCusto: Centros de custo
- Turno: Turnos de trabalho
- Bloco: Blocos de endereços/regiões
- Bairro: Bairros associados a blocos
"""

from app import db


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

    # =========================================================================
    # CAMPOS MULTI-TENANT - Configuração de conexão com bancos separados
    # =========================================================================
    # Identificador único para login (ex: 'gomobi', 'lear', 'nsg')
    slug_licenciado = db.Column(db.String(50), unique=True)
    # Configurações de conexão com banco de dados remoto
    db_host = db.Column(db.String(255))  # Host do banco (ex: render.com)
    db_name = db.Column(db.String(100))  # Nome do banco
    db_user = db.Column(db.String(100))  # Usuário do banco
    db_pass = db.Column(db.String(255))  # Senha (criptografada)
    db_port = db.Column(db.Integer, default=5432)  # Porta (padrão PostgreSQL)
    # Se TRUE, usa o banco local (DATABASE_URL do .env)
    # Se FALSE, usa as configurações db_host, db_name, etc.
    is_banco_local = db.Column(db.Boolean, default=True)

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
