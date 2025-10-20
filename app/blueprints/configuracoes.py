"""
Módulo de Configurações
=======================

Configurações e importações.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func, or_
from io import StringIO
import io
import csv

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp


@admin_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Pega os valores do formulário
        tempo_cortesia_str = request.form.get('tempo_cortesia')
        max_passageiros_str = request.form.get('max_passageiros')
        limite_fretado_str = request.form.get('limite_fretado')

        # Salva Tempo de Cortesia
        config_cortesia = Configuracao.query.filter_by(
            chave='TEMPO_CORTESIA_MINUTOS').first()
        if not config_cortesia:
            config_cortesia = Configuracao(
                chave='TEMPO_CORTESIA_MINUTOS', valor=tempo_cortesia_str)
            db.session.add(config_cortesia)
        else:
            config_cortesia.valor = tempo_cortesia_str

        # Salva Máximo de Passageiros
        config_passageiros = Configuracao.query.filter_by(
            chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        if not config_passageiros:
            config_passageiros = Configuracao(
                chave='MAX_PASSAGEIROS_POR_VIAGEM', valor=max_passageiros_str)
            db.session.add(config_passageiros)
        else:
            config_passageiros.valor = max_passageiros_str

        # Salva Limite de Fretado
        config_limite = Configuracao.query.filter_by(
            chave='limite_fretado').first()
        if not config_limite:
            config_limite = Configuracao(
                chave='limite_fretado', valor=limite_fretado_str)
            db.session.add(config_limite)
        else:
            config_limite.valor = limite_fretado_str

        db.session.commit()
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('admin.configuracoes'))

    # Se for GET, busca os valores atuais para exibir no formulário
    config_cortesia = Configuracao.query.filter_by(
        chave='TEMPO_CORTESIA_MINUTOS').first()
    config_passageiros = Configuracao.query.filter_by(
        chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
    config_limite = Configuracao.query.filter_by(
        chave='limite_fretado').first()
    
    # Valores padrão
    tempo_cortesia = config_cortesia.valor if config_cortesia else '30'
    max_passageiros = config_passageiros.valor if config_passageiros else '3'
    limite_fretado = config_limite.valor if config_limite else '9'

    return render_template('configuracoes.html', 
                         tempo_cortesia=tempo_cortesia,
                         max_passageiros=max_passageiros,
                         limite_fretado=limite_fretado)



# =============================================================================
# ROTA DE EXPORTAÇÃO CSV
# =============================================================================


@admin_bp.route('/admin/exportar_solicitacoes_csv')
@login_required
def exportar_solicitacoes_csv():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.home'))

    # --- LÓGICA DE FILTRO DE DATA (permanece a mesma) ---
    query_solicitacoes = Solicitacao.query
    data_inicio_str = request.args.get('data_inicio')
    data_fim_str = request.args.get('data_fim')

    if data_inicio_str:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        query_solicitacoes = query_solicitacoes.filter(
            Solicitacao.horario_entrada >= data_inicio)

    if data_fim_str:
        data_fim = datetime.strptime(
            data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query_solicitacoes = query_solicitacoes.filter(
            Solicitacao.horario_entrada <= data_fim)

    solicitacoes_filtradas = query_solicitacoes.order_by(
        Solicitacao.id.desc()).all()

    # --- NOVA LÓGICA DE GERAÇÃO DO CSV ---
    # 1. Cria um buffer de memória
    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    # 2. Escreve o cabeçalho
    cabecalho = [
        'ID Viagem', 'ID Solicitacao', 'Status', 'Tipo Corrida', 'Data Chegada',
        'Colaborador', 'Planta', 'Bloco', 'Supervisor', 'Motorista',
        'Valor (R$)', 'Valor Repasse (R$)'
    ]
    writer.writerow(cabecalho)

    # 3. Escreve todas as linhas de dados
    for solicitacao in solicitacoes_filtradas:
        bloco = solicitacao.colaborador.bloco
        linha = [
            solicitacao.viagem_id or '',
            solicitacao.id,
            solicitacao.status,
            solicitacao.tipo_corrida,
            solicitacao.horario_entrada.strftime('%d/%m/%Y %H:%M'),
            solicitacao.colaborador.nome,
            solicitacao.colaborador.planta,
            bloco.codigo_bloco if bloco else '',
            solicitacao.supervisor.nome,
            solicitacao.viagem.motorista.nome if solicitacao.viagem and solicitacao.viagem.motorista else '',
            f'{bloco.valor:.2f}' if bloco else '0.00',
            f'{bloco.valor_repasse:.2f}' if bloco else '0.00'
        ]
        writer.writerow(linha)

    # 4. Pega todo o conteúdo do buffer de memória
    csv_content = output.getvalue()

    # 5. Cria a resposta para o navegador forçar o download
    nome_arquivo = f"solicitacoes_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={nome_arquivo}"}
    )


# =============================================================================
# ROTAS DE IMPORTAÇÃO CSV
# =============================================================================


@admin_bp.route('/importacoes')
@login_required
def pagina_importacoes():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))
    return render_template('config/pagina_importacoes.html')


@admin_bp.route('/importar_colaboradores', methods=['GET', 'POST'])
@login_required
def importar_colaboradores():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename:
            flash('Por favor, selecione um arquivo CSV válido.', 'warning')
            return redirect(request.url)

        try:
            # Lê o conteúdo e decodifica, tratando o BOM do Windows
            decoded_content = file.stream.read().decode('utf-8-sig')
            lines = decoded_content.splitlines()
            csv_reader = csv.reader(lines, delimiter=';')

            # Pula o cabeçalho
            next(csv_reader, None)

            colaboradores_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):  # Começa em 2 por causa do cabeçalho
                # Validação para garantir que a linha não está vazia
                if not any(field.strip() for field in row):
                    continue

                # Limpa todos os campos
                row = [field.strip() for field in row]

                # Valida número de campos
                if len(row) < 7:
                    erros.append(f"Linha {i}: Número insuficiente de campos (esperado pelo menos 7, encontrado {len(row)})")
                    linhas_ignoradas += 1
                    continue

                # Desempacota os campos (com valores padrão para campos opcionais)
                # Formato: matricula;nome;empresa;planta;email;telefone;endereco;nro;bairro;cidade;uf;bloco;status
                matricula = row[0] if len(row) > 0 else ''
                nome = row[1] if len(row) > 1 else ''
                empresa_nome = row[2] if len(row) > 2 else ''
                planta_nome = row[3] if len(row) > 3 else ''
                email = row[4] if len(row) > 4 else ''
                telefone = row[5] if len(row) > 5 else ''
                endereco = row[6] if len(row) > 6 else ''
                nro = row[7] if len(row) > 7 else ''
                bairro = row[8] if len(row) > 8 else ''
                cidade = row[9] if len(row) > 9 else ''
                uf = row[10] if len(row) > 10 else ''
                bloco_codigo = row[11] if len(row) > 11 else ''
                status = row[12] if len(row) > 12 else 'Ativo'

                # Validações
                if not matricula or not nome:
                    erros.append(f"Linha {i}: Matrícula e nome são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Verifica se matrícula já existe
                if Colaborador.query.filter_by(matricula=matricula).first():
                    erros.append(f"Linha {i}: Matrícula '{matricula}' já existe no sistema")
                    linhas_ignoradas += 1
                    continue

                # Busca bloco (se fornecido)
                bloco_id = None
                if bloco_codigo:
                    bloco = Bloco.query.filter_by(codigo_bloco=bloco_codigo).first()
                    if bloco:
                        bloco_id = bloco.id
                    else:
                        erros.append(f"Linha {i}: Bloco '{bloco_codigo}' não encontrado (colaborador será criado sem bloco)")

                # Limpa e valida telefone (remove caracteres especiais e garante 11 dígitos)
                if telefone:
                    telefone_limpo = telefone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
                    if telefone_limpo and (not telefone_limpo.isdigit() or len(telefone_limpo) != 11):
                        erros.append(f"Linha {i}: Telefone '{telefone}' inválido (deve ter 11 dígitos). Colaborador será criado sem telefone.")
                        telefone_limpo = None
                else:
                    telefone_limpo = None

                # Busca empresa
                empresa = Empresa.query.filter_by(nome=empresa_nome).first()
                if not empresa:
                    erros.append(f"Linha {i}: Empresa '{empresa_nome}' não encontrada")
                    linhas_ignoradas += 1
                    continue

                # Busca planta
                planta = Planta.query.filter_by(nome=planta_nome, empresa_id=empresa.id).first()
                if not planta:
                    erros.append(f"Linha {i}: Planta '{planta_nome}' não encontrada para a empresa '{empresa_nome}'")
                    linhas_ignoradas += 1
                    continue

                # Valida status
                status_validos = ['Ativo', 'Inativo', 'Desligado', 'Ausente']
                if status and status not in status_validos:
                    status = 'Ativo'  # Valor padrão

                # Cria colaborador
                novo_colaborador = Colaborador(
                    matricula=matricula,
                    nome=nome,
                    empresa_id=empresa.id,
                    planta_id=planta.id,
                    email=email if email else None,
                    telefone=telefone_limpo,
                    endereco=endereco if endereco else None,
                    nro=nro if nro else None,
                    bairro=bairro if bairro else None,
                    cidade=cidade if cidade else None,
                    uf=uf if uf else None,
                    bloco_id=bloco_id,
                    status=status if status else 'Ativo'
                )
                
                db.session.add(novo_colaborador)
                colaboradores_adicionados += 1

            db.session.commit()

            # Mensagens de feedback
            if colaboradores_adicionados > 0:
                flash(f'{colaboradores_adicionados} colaboradores importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas por problemas nos dados.', 'warning')
                # Mostra os primeiros 5 erros
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')
            if colaboradores_adicionados == 0 and linhas_ignoradas == 0:
                flash('O arquivo estava vazio ou não continha dados válidos para importação.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro crítico ao processar o arquivo: {e}', 'danger')
            return redirect(request.url)

    # GET: Busca empresas e plantas para o template
    empresas = Empresa.query.all()
    plantas = Planta.query.all()
    return render_template('config/importar_colaboradores.html', empresas=empresas, plantas=plantas)


@admin_bp.route('/importar_supervisores', methods=['GET', 'POST'])
@login_required
def importar_supervisores():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename:
            flash('Por favor, selecione um arquivo CSV válido.', 'warning')
            return redirect(request.url)

        try:
            decoded_content = file.stream.read().decode('utf-8-sig')
            lines = decoded_content.splitlines()
            csv_reader = csv.reader(lines, delimiter=';')

            # Pula o cabeçalho
            next(csv_reader, None)

            supervisores_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):  # Começa em 2 por causa do cabeçalho
                if not any(field.strip() for field in row):
                    continue

                row = [field.strip() for field in row]

                # Valida número de campos
                if len(row) < 7:
                    erros.append(f"Linha {i}: Número insuficiente de campos (esperado 7, encontrado {len(row)})")
                    linhas_ignoradas += 1
                    continue

                # Ordem: matricula;nome;empresa;planta;email;senha;status
                matricula, nome, empresa_nome, planta_nome, email, senha, status = row[:7]

                # Validações
                if not matricula or not nome or not email or not senha:
                    erros.append(f"Linha {i}: Matrícula, nome, email e senha são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Verifica se matrícula já existe
                if Supervisor.query.filter_by(matricula=matricula).first():
                    erros.append(f"Linha {i}: Matrícula '{matricula}' já existe no sistema")
                    linhas_ignoradas += 1
                    continue

                # Verifica se email já existe
                if User.query.filter_by(email=email).first():
                    erros.append(f"Linha {i}: E-mail '{email}' já está em uso")
                    linhas_ignoradas += 1
                    continue

                # Busca empresa
                empresa = Empresa.query.filter_by(nome=empresa_nome).first()
                if not empresa:
                    erros.append(f"Linha {i}: Empresa '{empresa_nome}' não encontrada")
                    linhas_ignoradas += 1
                    continue

                # Busca planta
                planta = Planta.query.filter_by(nome=planta_nome, empresa_id=empresa.id).first()
                if not planta:
                    erros.append(f"Linha {i}: Planta '{planta_nome}' não encontrada para a empresa '{empresa_nome}'")
                    linhas_ignoradas += 1
                    continue

                # Valida status
                status_validos = ['Ativo', 'Inativo', 'Desligado', 'Ausente']
                if status and status not in status_validos:
                    status = 'Ativo'  # Valor padrão

                # Cria usuário
                hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
                new_user = User(email=email, password=hashed_password, role='supervisor')
                db.session.add(new_user)
                db.session.flush()  # Para obter o user_id

                # Cria supervisor
                novo_supervisor = Supervisor(
                    user_id=new_user.id,
                    matricula=matricula,
                    nome=nome,
                    empresa_id=empresa.id,
                    planta_id=planta.id,
                    email=email,
                    status=status if status else 'Ativo'
                )
                db.session.add(novo_supervisor)
                supervisores_adicionados += 1

            db.session.commit()

            # Mensagens de feedback
            if supervisores_adicionados > 0:
                flash(f'{supervisores_adicionados} supervisores importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas por problemas nos dados.', 'warning')
                # Mostra os primeiros 5 erros
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')
            if supervisores_adicionados == 0 and linhas_ignoradas == 0:
                flash('O arquivo estava vazio ou não continha dados válidos para importação.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='supervisores'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro crítico ao processar o arquivo: {e}', 'danger')
            return redirect(request.url)

    # GET: Busca empresas e plantas para o template
    empresas = Empresa.query.all()
    plantas = Planta.query.all()
    return render_template('config/importar_supervisores.html', empresas=empresas, plantas=plantas)


@admin_bp.route('/importar_motoristas', methods=['GET', 'POST'])
@login_required
def importar_motoristas():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename:
            flash('Por favor, selecione um arquivo CSV válido.', 'warning')
            return redirect(request.url)

        try:
            decoded_content = file.stream.read().decode('utf-8-sig')
            lines = decoded_content.splitlines()
            csv_reader = csv.reader(lines, delimiter=';')

            # Pula o cabeçalho
            next(csv_reader, None)

            motoristas_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):  # Começa em 2 por causa do cabeçalho
                if not any(field.strip() for field in row):
                    continue

                row = [field.strip() for field in row]

                # Valida número de campos
                if len(row) < 8:
                    erros.append(f"Linha {i}: Número insuficiente de campos (esperado 8, encontrado {len(row)})")
                    linhas_ignoradas += 1
                    continue

                # Ordem: nome;cpf_cnpj;email;senha;telefone;chave_pix;veiculo_nome;veiculo_placa
                nome, cpf_cnpj, email, senha, telefone, chave_pix, veiculo_nome, veiculo_placa = row[:8]

                # Validações
                if not nome or not cpf_cnpj or not email or not senha:
                    erros.append(f"Linha {i}: Nome, CPF/CNPJ, email e senha são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Verifica se email já existe
                if User.query.filter_by(email=email).first():
                    erros.append(f"Linha {i}: E-mail '{email}' já está em uso")
                    linhas_ignoradas += 1
                    continue

                # Verifica se CPF/CNPJ já existe
                if Motorista.query.filter_by(cpf_cnpj=cpf_cnpj).first():
                    erros.append(f"Linha {i}: CPF/CNPJ '{cpf_cnpj}' já está cadastrado")
                    linhas_ignoradas += 1
                    continue

                # Verifica se placa já existe (se fornecida)
                if veiculo_placa and Motorista.query.filter_by(veiculo_placa=veiculo_placa).first():
                    erros.append(f"Linha {i}: Placa '{veiculo_placa}' já está em uso")
                    linhas_ignoradas += 1
                    continue

                # Cria usuário
                hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
                new_user = User(email=email, password=hashed_password, role='motorista')
                db.session.add(new_user)
                db.session.flush()  # Para obter o user_id

                # Cria motorista
                novo_motorista = Motorista(
                    user_id=new_user.id,
                    nome=nome,
                    cpf_cnpj=cpf_cnpj,
                    email=email,
                    telefone=telefone if telefone else None,
                    chave_pix=chave_pix if chave_pix else None,
                    veiculo_nome=veiculo_nome if veiculo_nome else None,
                    veiculo_placa=veiculo_placa if veiculo_placa else None,
                    status='Ativo'
                )
                db.session.add(novo_motorista)
                motoristas_adicionados += 1

            db.session.commit()

            # Mensagens de feedback
            if motoristas_adicionados > 0:
                flash(f'{motoristas_adicionados} motoristas importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas por problemas nos dados.', 'warning')
                # Mostra os primeiros 5 erros
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')
            if motoristas_adicionados == 0 and linhas_ignoradas == 0:
                flash('O arquivo estava vazio ou não continha dados válidos para importação.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='motoristas'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ocorreu um erro crítico ao processar o arquivo: {e}', 'danger')
            return redirect(request.url)

    return render_template('config/importar_motoristas.html')



# =============================================================================
# APIs PARA SUPORTE AO FRONTEND
# =============================================================================

@admin_bp.route('/api/colaboradores/buscar')
@login_required
def api_buscar_colaboradores():
    """API para buscar colaboradores por nome ou matrícula"""
    query_str = request.args.get('q', '').strip()
    planta_id = request.args.get('planta_id', type=int)
    
    if len(query_str) < 2:
        return jsonify([])
    
    # Monta a query base
    query = Colaborador.query.filter(Colaborador.status == 'Ativo')
    
    # Filtra por planta se especificado
    if planta_id:
        query = query.filter(Colaborador.planta_id == planta_id)
    elif current_user.role == 'supervisor':
        # Supervisor só vê colaboradores das suas plantas
        plantas_ids = [p.id for p in current_user.supervisor.plantas]
        if plantas_ids:
            query = query.filter(Colaborador.planta_id.in_(plantas_ids))
    
    # Busca por nome ou matrícula
    query = query.filter(
        or_(
            Colaborador.nome.ilike(f'%{query_str}%'),
            Colaborador.matricula.ilike(f'%{query_str}%')
        )
    ).limit(10)
    
    colaboradores = query.all()
    
    # Retorna JSON com os dados necessários
    resultado = []
    for colab in colaboradores:
        resultado.append({
            'id': colab.id,
            'nome': colab.nome,
            'matricula': colab.matricula,
            'bloco': colab.bloco.codigo_bloco if colab.bloco else 'N/A',
            'bloco_id': colab.bloco_id,
            'turnos': [{'id': t.id, 'nome': t.nome} for t in colab.turnos]
        })
    
    return jsonify(resultado)


@admin_bp.route('/api/empresas/<int:empresa_id>/plantas')
@login_required
def api_plantas_por_empresa(empresa_id):
    """API para buscar plantas de uma empresa"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Acesso negado'}), 403
    
    plantas = Planta.query.filter_by(empresa_id=empresa_id).order_by(Planta.nome).all()
    
    resultado = [{'id': p.id, 'nome': p.nome} for p in plantas]
    
    return jsonify(resultado)


@admin_bp.route('/api/plantas/<int:planta_id>/supervisores')
@login_required
def api_supervisores_por_planta(planta_id):
    """API para buscar supervisores de uma planta"""
    supervisores = Supervisor.query.filter_by(
        planta_id=planta_id,
        status='Ativo'
    ).order_by(Supervisor.nome).all()
    
    resultado = [{'id': s.id, 'nome': s.nome, 'matricula': s.matricula} for s in supervisores]
    
    return jsonify(resultado)


@admin_bp.route('/api/plantas/<int:planta_id>/turnos')
@login_required
def api_turnos_por_planta(planta_id):
    """API para buscar turnos de uma planta"""
    turnos = Turno.query.filter_by(planta_id=planta_id).order_by(Turno.horario_inicio).all()
    
    resultado = []
    for turno in turnos:
        resultado.append({
            'id': turno.id,
            'nome': turno.nome,
            'horario_inicio': turno.horario_inicio.strftime('%H:%M') if turno.horario_inicio else '',
            'horario_fim': turno.horario_fim.strftime('%H:%M') if turno.horario_fim else ''
        })
    
    return jsonify(resultado)


# =============================================================================
# ROTAS DE AGRUPAMENTO DE VIAGENS
# =============================================================================

