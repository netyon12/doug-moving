"""
Modelos de Processos Operacionais
=================================

Classes relacionadas ao fluxo operacional do sistema:
- Viagem: Viagens agrupadas executadas por motoristas
- Solicitacao: Solicitações de transporte criadas por supervisores
- ViagemHoraParada: Registro de horas paradas em viagens
"""

from app import db
from app.models import horario_brasil
from datetime import datetime
from app.config.tenant_utils import get_tenant_session


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
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey(
        'bloco.id'), nullable=True)  # Bloco principal
    # "1,3,5" para múltiplos blocos
    blocos_ids = db.Column(db.String(255), nullable=True)

    # === TIPO DE VIAGEM ===
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    tipo_corrida = db.Column(db.String(20), nullable=False)

    # === HORÁRIOS ===
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)

    # === PASSAGEIROS ===
    colaboradores_ids = db.Column(
        db.Text, nullable=True)  # JSON: "[1, 5, 8, 12]"
    quantidade_passageiros = db.Column(
        db.Integer, default=0)  # Calculado automaticamente

    # === MOTORISTA E VEÍCULO ===
    motorista_id = db.Column(
        db.Integer, db.ForeignKey('motorista.id'), nullable=True)
    # Preenchido quando motorista aceitar
    nome_motorista = db.Column(db.String(150), nullable=True)
    # Preenchido quando motorista aceitar
    placa_veiculo = db.Column(db.String(20), nullable=True)

    # === VALORES FINANCEIROS ===
    # Valor total da viagem (MAIOR valor entre solicitações)
    valor = db.Column(db.Numeric(10, 2), nullable=True)
    # Valor de repasse para o motorista
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=True)

    # === STATUS E CONTROLE ===
    status = db.Column(db.String(20), nullable=False, default='Pendente')
    motivo_cancelamento = db.Column(
        db.Text, nullable=True)  # Preenchido se cancelada
    cancelado_por_user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True)  # Quem cancelou

    # === AUDITORIA E TIMESTAMPS ===
    created_by_user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True)  # Quem criou (admin/supervisor)
    data_criacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil)
    data_atualizacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil, onupdate=horario_brasil)
    # Quando motorista iniciou
    data_inicio = db.Column(db.DateTime, nullable=True)
    # Quando motorista finalizou
    data_finalizacao = db.Column(db.DateTime, nullable=True)
    data_cancelamento = db.Column(
        db.DateTime, nullable=True)  # Quando foi cancelada

    # === RELACIONAMENTOS ===
    empresa = db.relationship('Empresa', backref='viagens')
    planta = db.relationship('Planta', backref='viagens')
    bloco = db.relationship('Bloco', backref='viagens')
    motorista = db.relationship('Motorista', back_populates='viagens')
    solicitacoes = db.relationship(
        'Solicitacao', back_populates='viagem', cascade="all, delete-orphan")
    created_by = db.relationship(
        'User', foreign_keys=[created_by_user_id], backref='viagens_criadas')
    cancelado_por = db.relationship(
        'User', foreign_keys=[cancelado_por_user_id], backref='viagens_canceladas')

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

        # Atualiza status do motorista
        motorista.status = 'Agendado'
        get_tenant_session().add(motorista)  # Garante que a alteração seja persistida
        # Atualiza status das solicitações
        if self.solicitacoes:
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

        # Atualiza status do motorista para Ocupado
        self.motorista.status = 'Ocupado'
        get_tenant_session().add(self.motorista)  # Garante que a alteração seja persistida
        # Atualiza status das solicitações
        if self.solicitacoes:
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

        # Atualiza status do motorista para Disponível
        self.motorista.status = 'Disponível'
        get_tenant_session().add(self.motorista)  # Garante que a alteração seja persistida
        # Atualiza status das solicitações
        if self.solicitacoes:
            for solicitacao in self.solicitacoes:
                solicitacao.status = 'Finalizada'

            # MELHORIA 1: Se é viagem de desligamento, altera status do colaborador para 'Desligado'
            if self.tipo_corrida == 'desligamento':
                for solicitacao in self.solicitacoes:
                    if solicitacao.colaborador:
                        solicitacao.colaborador.status = 'Desligado'

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

        # Salva referência ao motorista antes de desassociar
        motorista_obj = self.motorista

        # Remove associação com motorista
        self.motorista_id = None
        self.nome_motorista = None
        self.placa_veiculo = None

        # Volta status para Pendente (apenas a VIAGEM, não as solicitações)
        self.status = 'Pendente'
        self.data_atualizacao = datetime.utcnow()

        # Reverte status das solicitações para Agrupada
        for solicitacao in self.solicitacoes:
            solicitacao.status = 'Agrupada'

        # Volta status do motorista para Disponível
        if motorista_obj:
            motorista_obj.status = 'Disponível'
            get_tenant_session().add(motorista_obj)  # Garante que a alteração seja persistida
        return True


class Solicitacao(db.Model):
    __tablename__ = 'solicitacao'
    id = db.Column(db.Integer, primary_key=True)

    # Relacionamentos principais
    colaborador_id = db.Column(db.Integer, db.ForeignKey(
        'colaborador.id'), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey(
        'supervisor.id'), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey(
        'empresa.id'), nullable=False)
    planta_id = db.Column(db.Integer, db.ForeignKey(
        'planta.id'), nullable=False)
    bloco_id = db.Column(db.Integer, db.ForeignKey('bloco.id'), nullable=False)

    # Tipo de linha e corrida
    tipo_linha = db.Column(db.String(10), nullable=False)  # 'FIXA' ou 'EXTRA'
    # 'entrada', 'saida', 'entrada_saida', 'desligamento'
    tipo_corrida = db.Column(db.String(20), nullable=False)

    # Horários
    horario_entrada = db.Column(db.DateTime, nullable=True)
    horario_saida = db.Column(db.DateTime, nullable=True)
    horario_desligamento = db.Column(db.DateTime, nullable=True)

    # Turnos (referências aos turnos calculados)
    turno_entrada_id = db.Column(
        db.Integer, db.ForeignKey('turno.id'), nullable=True)
    turno_saida_id = db.Column(
        db.Integer, db.ForeignKey('turno.id'), nullable=True)
    turno_desligamento_id = db.Column(
        db.Integer, db.ForeignKey('turno.id'), nullable=True)

    # Status e viagem/fretado
    # Pendente, Agrupada, Fretado, Finalizada, Cancelada
    status = db.Column(db.String(20), nullable=False, default='Pendente')
    viagem_id = db.Column(db.Integer, db.ForeignKey(
        'viagem.id'), nullable=True)  # NULL até agrupar
    fretado_id = db.Column(db.Integer, db.ForeignKey(
        'fretado.id'), nullable=True)  # NULL até agrupar como fretado

    # Valores financeiros
    # Valor baseado em ValorBlocoTurno
    valor = db.Column(db.Numeric(10, 2), nullable=True)
    # Valor de repasse para o motorista
    valor_repasse = db.Column(db.Numeric(10, 2), nullable=True)

    # Rastreamento de quem criou
    created_by_user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'), nullable=True)  # Usuário que criou a solicitação

    # Timestamps
    data_criacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil)
    data_atualizacao = db.Column(
        db.DateTime, nullable=False, default=horario_brasil, onupdate=horario_brasil)

    # Relacionamentos
    colaborador = db.relationship('Colaborador', backref='solicitacoes')
    supervisor = db.relationship('Supervisor', backref='solicitacoes')
    empresa = db.relationship('Empresa', backref='solicitacoes')
    planta = db.relationship('Planta', backref='solicitacoes')
    bloco = db.relationship('Bloco', backref='solicitacoes')
    turno_entrada = db.relationship('Turno', foreign_keys=[turno_entrada_id])
    turno_saida = db.relationship('Turno', foreign_keys=[turno_saida_id])
    turno_desligamento = db.relationship(
        'Turno', foreign_keys=[turno_desligamento_id])
    viagem = db.relationship('Viagem', back_populates='solicitacoes')
    fretado = db.relationship(
        'Fretado', backref='solicitacoes', foreign_keys='Solicitacao.fretado_id')
    created_by = db.relationship(
        'User', foreign_keys=[created_by_user_id], backref='solicitacoes_criadas')

    def get_criador_nome(self):
        """
        Retorna o nome de quem criou a solicitação.
        
        IMPORTANTE: Em arquitetura multi-banco, o relacionamento created_by
        pode não funcionar corretamente. Por isso, buscamos manualmente
        o usuário no banco atual usando created_by_user_id.
        """
        if not self.created_by_user_id:
            return 'N/A'
        
        # Busca usuário no banco atual
        from app.models import User
        from app.config.tenant_utils import query_tenant
        
        try:
            user = query_tenant(User).filter_by(id=self.created_by_user_id).first()
            
            if not user:
                return 'N/A'
            
            # Retorna nome baseado no role
            if user.role == 'supervisor':
                from app.models import Supervisor
                supervisor = query_tenant(Supervisor).filter_by(user_id=user.id).first()
                return supervisor.nome if supervisor else user.email
            elif user.role == 'gerente':
                from app.models import Gerente
                gerente = query_tenant(Gerente).filter_by(user_id=user.id).first()
                return gerente.nome if gerente else user.email
            elif user.role == 'admin':
                return 'Administrador'
            elif user.role == 'operador':
                return 'Operador'
            else:
                return user.email
        except Exception as e:
            print(f"[ERRO] get_criador_nome: {e}")
            return 'N/A'

    def __repr__(self):
        return f'<Solicitacao {self.id} - {self.colaborador.nome} - {self.tipo_corrida}>'


class ViagemHoraParada(db.Model):
    """
    Modelo para registrar cobranças de hora parada em viagens.

    Hora parada é cobrada quando o colaborador atrasa para iniciar a viagem.
    A cada 30 minutos de atraso, é acrescentado um valor fixo na viagem e no repasse do motorista.

    Regras:
    - Apenas 1 registro de hora parada por viagem (UNIQUE constraint)
    - Valores configuráveis via tabela 'configuracao'
    - Apenas Admin pode adicionar/editar/excluir
    - Cálculo automático baseado na diferença entre horário agendado e horário real de início
    """
    __tablename__ = 'viagem_hora_parada'

    # === IDENTIFICAÇÃO ===
    id = db.Column(db.Integer, primary_key=True)
    viagem_id = db.Column(db.Integer, db.ForeignKey(
        'viagem.id'), nullable=False, unique=True)

    # === CÁLCULO DO ATRASO ===
    # 'entrada', 'saida', 'desligamento'
    tipo_corrida = db.Column(db.String(20), nullable=False)
    # Horário que deveria iniciar
    horario_agendado = db.Column(db.DateTime, nullable=False)
    # Horário que realmente iniciou (data_inicio da viagem)
    horario_real_inicio = db.Column(db.DateTime, nullable=False)
    minutos_atraso = db.Column(
        db.Integer, nullable=False)  # Diferença em minutos
    # Quantos períodos de 30min cobrar
    periodos_30min = db.Column(db.Integer, nullable=False)

    # === VALORES FINANCEIROS ===
    # Valor adicional na viagem (ex: 71,02 x períodos)
    valor_adicional = db.Column(db.Numeric(10, 2), nullable=False)
    # Repasse adicional ao motorista (ex: 29,00 x períodos)
    repasse_adicional = db.Column(db.Numeric(10, 2), nullable=False)

    # === AUDITORIA ===
    observacoes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=datetime.utcnow)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True)

    # === RELACIONAMENTOS ===
    viagem = db.relationship('Viagem', backref=db.backref(
        'hora_parada', uselist=False, cascade="all, delete-orphan"))
    created_by = db.relationship('User', backref='horas_paradas_criadas')

    def __repr__(self):
        return f'<ViagemHoraParada Viagem#{self.viagem_id} - {self.periodos_30min}x30min - R$ {self.valor_adicional}>'

    def to_dict(self):
        """Converte o registro para dicionário."""
        return {
            'id': self.id,
            'viagem_id': self.viagem_id,
            'tipo_corrida': self.tipo_corrida,
            'horario_agendado': self.horario_agendado.isoformat() if self.horario_agendado else None,
            'horario_real_inicio': self.horario_real_inicio.isoformat() if self.horario_real_inicio else None,
            'minutos_atraso': self.minutos_atraso,
            'periodos_30min': self.periodos_30min,
            'valor_adicional': float(self.valor_adicional) if self.valor_adicional else 0.00,
            'repasse_adicional': float(self.repasse_adicional) if self.repasse_adicional else 0.00,
            'observacoes': self.observacoes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_user_id': self.created_by_user_id,
            'created_by_name': self.created_by.username if self.created_by else None
        }

    @staticmethod
    def calcular_periodos(minutos_atraso):
        """
        Calcula quantos períodos de 30min devem ser cobrados.

        Regra: A cada 30 minutos de atraso, cobra 1 período.
        - 1 a 30 minutos = 1 período
        - 31 a 60 minutos = 2 períodos
        - 61 a 90 minutos = 3 períodos
        - etc.

        Args:
            minutos_atraso (int): Minutos de atraso

        Returns:
            int: Número de períodos de 30min a cobrar
        """
        import math
        if minutos_atraso <= 0:
            return 0
        return math.ceil(minutos_atraso / 30)

    @staticmethod
    def obter_valores_configurados():
        """
        Obtém os valores configurados de hora parada.

        Returns:
            tuple: (valor_periodo, repasse_periodo)
        """
        from app.models import Configuracao

        # Valores padrão
        valor_periodo = 71.02
        repasse_periodo = 29.00

        # Busca valores configurados
        config_valor = Configuracao.query.filter_by(
            chave='hora_parada_valor_periodo').first()
        config_repasse = Configuracao.query.filter_by(
            chave='hora_parada_repasse_periodo').first()

        if config_valor:
            try:
                valor_periodo = float(config_valor.valor)
            except ValueError:
                pass

        if config_repasse:
            try:
                repasse_periodo = float(config_repasse.valor)
            except ValueError:
                pass

        return (valor_periodo, repasse_periodo)
