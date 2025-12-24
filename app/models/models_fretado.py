"""
Modelo de Fretado
================

Classe relacionada ao módulo de fretados:
- Fretado: Gestão de viagens fretadas (colaboradores que vão de fretado)
"""

from app import db
from app.models import horario_brasil


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
    solicitacao_id = db.Column(db.Integer, db.ForeignKey(
        'solicitacao.id'), nullable=False)  # ID da solicitação original
    colaborador_id = db.Column(db.Integer, db.ForeignKey(
        'colaborador.id'), nullable=False)  # ID do colaborador

    # === DADOS DO COLABORADOR ===
    nome_colaborador = db.Column(
        db.String(150), nullable=False)  # Nome do colaborador
    # Matrícula do colaborador
    matricula = db.Column(db.String(50), nullable=True)
    # Telefone do colaborador
    telefone = db.Column(db.String(20), nullable=True)

    # === ENDEREÇO DO COLABORADOR ===
    endereco = db.Column(db.String(255), nullable=True)  # Endereço completo
    bairro = db.Column(db.String(100), nullable=True)  # Bairro
    cidade = db.Column(db.String(100), nullable=True)  # Cidade

    # === LOCALIZAÇÃO E CONTEXTO ===
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey(
        'bloco.id'), nullable=True)  # Bloco do colaborador
    # Ex: "CPV1", "SJC1" - raiz do código do bloco
    grupo_bloco = db.Column(db.String(50), nullable=True)

    # === TIPO DE VIAGEM ===
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    tipo_corrida = db.Column(db.String(20), nullable=False)

    # === HORÁRIOS ===
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)

    # === STATUS E CONTROLE ===
    status = db.Column(db.String(20), nullable=False,
                       default='Fretado')  # Status: 'Fretado'
    observacoes = db.Column(db.Text, nullable=True)  # Observações gerais

    # === AUDITORIA E TIMESTAMPS ===
    created_by_user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True)  # Quem criou
    data_criacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil)
    data_atualizacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil, onupdate=horario_brasil)

    # === RELACIONAMENTOS ===
    solicitacao = db.relationship('Solicitacao', foreign_keys=[solicitacao_id])
    colaborador = db.relationship('Colaborador', foreign_keys=[colaborador_id])
    empresa = db.relationship('Empresa', foreign_keys=[empresa_id])
    planta = db.relationship('Planta', foreign_keys=[planta_id])
    bloco = db.relationship('Bloco', foreign_keys=[bloco_id])
    created_by = db.relationship(
        'User', foreign_keys=[created_by_user_id], backref='fretados_criados')

    def __repr__(self):
        return f'<Fretado {self.id} - {self.nome_colaborador} - {self.grupo_bloco}>'

    # === MÉTODOS AUXILIARES ===

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
            'solicitacao_id': self.solicitacao_id,
            'colaborador_id': self.colaborador_id,
            'nome_colaborador': self.nome_colaborador,
            'matricula': self.matricula,
            'telefone': self.telefone,
            'endereco': self.endereco,
            'bairro': self.bairro,
            'cidade': self.cidade,
            'empresa_id': self.empresa_id,
            'empresa_nome': self.empresa.nome if self.empresa else None,
            'planta_id': self.planta_id,
            'planta_nome': self.planta.nome if self.planta else None,
            'bloco_id': self.bloco_id,
            'bloco_codigo': self.bloco.codigo_bloco if self.bloco else None,
            'grupo_bloco': self.grupo_bloco,
            'tipo_linha': self.tipo_linha,
            'tipo_corrida': self.tipo_corrida,
            'horario_entrada': self.horario_entrada.isoformat() if self.horario_entrada else None,
            'horario_saida': self.horario_saida.isoformat() if self.horario_saida else None,
            'horario_desligamento': self.horario_desligamento.isoformat() if self.horario_desligamento else None,
            'status': self.status,
            'observacoes': self.observacoes,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
        }
