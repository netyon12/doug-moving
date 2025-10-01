# app/models.py
from . import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    
    supervisor = db.relationship('Supervisor', back_populates='user', uselist=False)
    motorista = db.relationship('Motorista', back_populates='user', uselist=False)

class Supervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    planta = db.Column(db.String(100))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    telefone = db.Column(db.String(20))
    turno = db.Column(db.String(50))
    gerente_responsavel = db.Column(db.String(100))
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'))
    
    user = db.relationship('User', back_populates='supervisor')
    bloco = db.relationship('Bloco')

class Colaborador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    planta = db.Column(db.String(100))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    turno = db.Column(db.String(50))
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'))
    
    bloco = db.relationship('Bloco')

class Motorista(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    planta = db.Column(db.String(100))
    endereco = db.Column(db.String(100))
    nro = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    telefone = db.Column(db.String(20))
    pix = db.Column(db.String(100))
    veiculo = db.Column(db.String(100))
    ano_veiculo = db.Column(db.Integer)
    cor_veiculo = db.Column(db.String(50))
    placa_veiculo = db.Column(db.String(10), unique=True)
    km_veiculo = db.Column(db.Float)
    observacoes_gerais = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Disponível')
    
    user = db.relationship('User', back_populates='motorista')
    viagens = db.relationship('Viagem', back_populates='motorista')

class Bloco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_bloco = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Float, nullable=False)
    valor_repasse = db.Column(db.Float, nullable=False)

class Viagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorista_id = db.Column(db.Integer, db.ForeignKey('motorista.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Em Andamento')
    data_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_finalizacao = db.Column(db.DateTime)
    
    motorista = db.relationship('Motorista', back_populates='viagens')
    solicitacoes = db.relationship('Solicitacao', back_populates='viagem')

class Solicitacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    colaborador_id = db.Column(db.Integer, db.ForeignKey('colaborador.id'), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('supervisor.id'), nullable=False)
    horario_chegada = db.Column(db.DateTime, nullable=False)
    tipo_corrida = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pendente')
    viagem_id = db.Column(db.Integer, db.ForeignKey('viagem.id'), nullable=True)
    
    colaborador = db.relationship('Colaborador')
    supervisor = db.relationship('Supervisor')
    viagem = db.relationship('Viagem', back_populates='solicitacoes')







    