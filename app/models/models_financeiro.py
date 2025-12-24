"""
Modelos Financeiros
==================

Classes relacionadas à gestão financeira:
- FinContasReceber: Contas a receber (títulos das empresas)
- FinReceberViagens: Associação de viagens a títulos a receber
- FinContasPagar: Contas a pagar (títulos dos motoristas)
- FinPagarViagens: Associação de viagens a títulos a pagar
"""

from app import db
from datetime import datetime


class FinContasReceber(db.Model):
    """Modelo para Contas a Receber (Títulos das Empresas)"""
    __tablename__ = 'fin_contas_receber'

    id = db.Column(db.Integer, primary_key=True)
    numero_titulo = db.Column(db.String(50), unique=True, nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_recebimento = db.Column(db.Date)
    # Aberto, Recebido, Vencido, Cancelado
    status = db.Column(db.String(20), nullable=False, default='Aberto')
    numero_nota_fiscal = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    empresa = db.relationship('Empresa', backref='titulos_receber')
    created_by = db.relationship('User', backref='titulos_receber_criados')
    viagens = db.relationship(
        'FinReceberViagens', back_populates='conta_receber', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<FinContasReceber {self.numero_titulo} - {self.empresa.nome if self.empresa else "N/A"}>'


class FinReceberViagens(db.Model):
    """Modelo para vincular viagens aos títulos a receber"""
    __tablename__ = 'fin_receber_viagens'

    id = db.Column(db.Integer, primary_key=True)
    conta_receber_id = db.Column(db.Integer, db.ForeignKey(
        'fin_contas_receber.id', ondelete='CASCADE'), nullable=False)
    viagem_id = db.Column(db.Integer, db.ForeignKey(
        'viagem.id'), nullable=False)
    valor_viagem = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    conta_receber = db.relationship(
        'FinContasReceber', back_populates='viagens')
    viagem = db.relationship('Viagem', backref='titulo_receber')

    # Constraint única para evitar duplicação
    __table_args__ = (db.UniqueConstraint('conta_receber_id',
                      'viagem_id', name='_conta_viagem_receber_uc'),)

    def __repr__(self):
        return f'<FinReceberViagens Título:{self.conta_receber_id} Viagem:{self.viagem_id}>'


class FinContasPagar(db.Model):
    """Modelo para Contas a Pagar (Títulos dos Motoristas)"""
    __tablename__ = 'fin_contas_pagar'

    id = db.Column(db.Integer, primary_key=True)
    numero_titulo = db.Column(db.String(50), unique=True, nullable=False)
    motorista_id = db.Column(db.Integer, db.ForeignKey(
        'motorista.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    data_emissao = db.Column(db.Date, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.Date)
    # Aberto, Pago, Vencido, Cancelado
    status = db.Column(db.String(20), nullable=False, default='Aberto')
    # PIX, Transferência, Dinheiro, etc.
    forma_pagamento = db.Column(db.String(50))
    comprovante_pagamento = db.Column(db.String(255))  # Caminho do arquivo
    observacoes = db.Column(db.Text)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    motorista = db.relationship('Motorista', backref='titulos_pagar')
    created_by = db.relationship('User', backref='titulos_pagar_criados')
    viagens = db.relationship(
        'FinPagarViagens', back_populates='conta_pagar', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<FinContasPagar {self.numero_titulo} - {self.motorista.nome if self.motorista else "N/A"}>'


class FinPagarViagens(db.Model):
    """Modelo para vincular viagens aos títulos a pagar"""
    __tablename__ = 'fin_pagar_viagens'

    id = db.Column(db.Integer, primary_key=True)
    conta_pagar_id = db.Column(db.Integer, db.ForeignKey(
        'fin_contas_pagar.id', ondelete='CASCADE'), nullable=False)
    viagem_id = db.Column(db.Integer, db.ForeignKey(
        'viagem.id'), nullable=False)
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    conta_pagar = db.relationship('FinContasPagar', back_populates='viagens')
    viagem = db.relationship('Viagem', backref='titulo_pagar')

    # Constraint única para evitar duplicação
    __table_args__ = (db.UniqueConstraint('conta_pagar_id',
                      'viagem_id', name='_conta_viagem_pagar_uc'),)

    def __repr__(self):
        return f'<FinPagarViagens Título:{self.conta_pagar_id} Viagem:{self.viagem_id}>'
