from flask import Blueprint, render_template, request, flash, redirect, url_for
from datetime import datetime, timedelta
from sqlalchemy import or_
from app import db
from app.models import Colaborador, Viagem, Motorista

# Criação do Blueprint para as rotas de consulta
consulta_bp = Blueprint('consulta', __name__)

# Função auxiliar para obter o horário de Brasília (UTC-3)


def horario_brasil():
    return datetime.utcnow() - timedelta(hours=3)


@consulta_bp.route('/consulta-viagens', methods=['GET', 'POST'])
def consulta_viagens():
    """
    Rota para a consulta pública de viagens por matrícula.
    GET: Exibe o formulário de consulta.
    POST: Processa a matrícula e exibe o resultado da viagem mais próxima.
    """

    if request.method == 'POST':
        matricula = request.form.get('matricula')

        if not matricula:
            flash('Por favor, digite a matrícula para consultar.', 'danger')
            return redirect(url_for('consulta.consulta_viagens'))

        # 1. Buscar colaborador por matrícula
        colaborador = Colaborador.query.filter_by(matricula=matricula).first()

        if not colaborador:
            flash('Matrícula inválida. Colaborador não encontrado.', 'danger')
            # Retorna para o formulário sem resultado
            return render_template('consulta_viagens.html', resultado=None)

        # 2. Buscar viagens do colaborador com status 'Agendada' OU 'Pendente'
        #    e data/hora FUTURAS (>= data/hora atual)

        # O campo 'colaboradores_ids' na tabela Viagem é um TEXT que armazena uma lista JSON de IDs.
        # A busca deve ser feita verificando se o ID do colaborador está contido nessa string.

        agora_brasil = horario_brasil()

        # A lógica de busca deve considerar o horário de entrada, saída ou desligamento,
        # dependendo do tipo_corrida. Como a Viagem é um agrupamento de Solicitações,
        # vamos usar o campo de data/hora mais relevante para a viagem.
        # No modelo Viagem, não há um campo único 'data_hora', mas sim 'horario_entrada', 'horario_saida', etc.
        # Para simplificar a consulta, vamos buscar a viagem mais próxima no futuro.

        # Para a consulta, vamos buscar todas as viagens onde o ID do colaborador está na lista
        # de colaboradores_ids (usando LIKE, que é comum para JSON/Text em SQL)
        # e o status é 'Pendente' ou 'Agendada'.

        # A busca por data futura é complexa no modelo Viagem, pois depende do tipo_corrida.
        # Vamos simplificar e buscar a viagem mais próxima no futuro, assumindo que a data
        # mais relevante é a que está preenchida e é a mais próxima de agora.

        # Vamos buscar todas as viagens futuras (Pendente ou Agendada) que contenham o ID do colaborador.

        # Viagens Pendentes ou Agendadas
        # A busca deve ser precisa: [ID], [ID, ...], ..., ID], ..., ID, ...
        # Buscamos a string exata do ID do colaborador, cercada por caracteres de separação JSON ([, ], ,)
        colaborador_id_str = str(colaborador.id)

        viagens_candidatas = Viagem.query.filter(
            # Busca o ID do colaborador cercado por caracteres de separação JSON
            or_(
                # Começo da lista: [10, ...
                Viagem.colaboradores_ids.like(f'[{colaborador_id_str},%'),
                Viagem.colaboradores_ids.like(f'[{colaborador_id_str}]'),

                # Meio da lista: ...,10,... (cobre com e sem espaço)
                Viagem.colaboradores_ids.like(
                    f'%, {colaborador_id_str},%'),  # COM espaço
                Viagem.colaboradores_ids.like(
                    f'%,{colaborador_id_str},%'),   # SEM espaço

                # Fim da lista: ...,10] (cobre com e sem espaço)
                Viagem.colaboradores_ids.like(
                    f'%, {colaborador_id_str}]'),   # COM espaço
                Viagem.colaboradores_ids.like(
                    f'%,{colaborador_id_str}]'),    # SEM espaço

                # Lista com um único elemento: [10]
                Viagem.colaboradores_ids == f'[{colaborador_id_str}]'
            ),
            or_(Viagem.status == 'Pendente', Viagem.status == 'Agendada')
        ).all()

        viagem_mais_proxima = None
        min_diff = timedelta.max

        for viagem in viagens_candidatas:
            data_viagem = None

            # Determina a data/hora mais relevante para a viagem
            if viagem.tipo_corrida == 'entrada' and viagem.horario_entrada:
                data_viagem = viagem.horario_entrada
            elif viagem.tipo_corrida == 'saida' and viagem.horario_saida:
                data_viagem = viagem.horario_saida
            elif viagem.tipo_corrida == 'desligamento' and viagem.horario_desligamento:
                data_viagem = viagem.horario_desligamento

            if data_viagem and data_viagem > agora_brasil:
                diff = data_viagem - agora_brasil
                if diff < min_diff:
                    min_diff = diff
                    viagem_mais_proxima = viagem

        # 3. Pegar apenas a PRIMEIRA (mais próxima)
        if viagem_mais_proxima:

            # Formatação da data/hora
            data_hora_formatada = ""
            if viagem_mais_proxima.tipo_corrida == 'entrada' and viagem_mais_proxima.horario_entrada:
                data_hora_formatada = viagem_mais_proxima.horario_entrada.strftime(
                    '%d/%m/%Y %H:%M') + " (Entrada)"
            elif viagem_mais_proxima.tipo_corrida == 'saida' and viagem_mais_proxima.horario_saida:
                data_hora_formatada = viagem_mais_proxima.horario_saida.strftime(
                    '%d/%m/%Y %H:%M') + " (Saída)"
            elif viagem_mais_proxima.tipo_corrida == 'desligamento' and viagem_mais_proxima.horario_desligamento:
                data_hora_formatada = viagem_mais_proxima.horario_desligamento.strftime(
                    '%d/%m/%Y %H:%M') + " (Desligamento)"

            resultado = {
                'status': viagem_mais_proxima.status,
                'nome_colaborador': colaborador.nome,
                'id_viagem': viagem_mais_proxima.id,
                'data_hora': data_hora_formatada,
                'tipo_corrida': viagem_mais_proxima.tipo_corrida.capitalize(),
                'nome_motorista': "Aguardando Motorista" if viagem_mais_proxima.status == 'Pendente' else viagem_mais_proxima.nome_motorista,
                'modelo_veiculo': "N/A",
                'placa_veiculo': viagem_mais_proxima.placa_veiculo if viagem_mais_proxima.placa_veiculo else "N/A",
                'cor_veiculo': "N/A",
            }

            # Se for Pendente, ajusta a mensagem
            if viagem_mais_proxima.status == 'Pendente':
                flash(
                    f"Sua Viagem ID {viagem_mais_proxima.id} ainda está com status de 'Pendente' e aguarda a confirmação de um motorista. Por favor, consulte novamente mais tarde.", 'warning')

            # Se for Agendada, a mensagem de sucesso será exibida no template
            if viagem_mais_proxima.status == 'Agendada' and viagem_mais_proxima.motorista_id:
                motorista = Motorista.query.get(
                    viagem_mais_proxima.motorista_id)
                if motorista:
                    resultado['modelo_veiculo'] = motorista.veiculo_nome
                    resultado['cor_veiculo'] = motorista.veiculo_cor

                # A mensagem de sucesso será exibida no template, não precisa de flash aqui.

            return render_template('consulta_viagens.html', resultado=resultado)

        else:
            # 4. Sem viagem
            resultado = {
                'status': 'Nenhuma',
                'nome_colaborador': colaborador.nome,
            }
            flash(
                f"Olá {colaborador.nome}, não encontramos nenhuma viagem futura agendada ou pendente para sua matrícula.", 'info')
            return render_template('consulta_viagens.html', resultado=resultado)

    # Rota GET (exibe o formulário)
    return render_template('consulta_viagens.html', resultado=None)

# É necessário registrar o Blueprint no arquivo principal da aplicação (app/__init__.py)
# para que as rotas sejam reconhecidas.
# Exemplo: app.register_blueprint(consulta_bp)
