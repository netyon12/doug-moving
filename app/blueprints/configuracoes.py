"""
Módulo de Configurações - Versão Expandida
==========================================

Configurações e importações com todos os campos disponíveis.
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
import re

from .. import db
from ..models import (
    User, Empresa, Planta, CentroCusto, Turno, Bloco, Bairro,
    Gerente, Supervisor, Colaborador, Motorista, Solicitacao, Viagem, Configuracao
)
from ..decorators import permission_required
from app import query_filters

from .admin import admin_bp


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def validar_cpf_cnpj(cpf_cnpj):
    """Valida formato básico de CPF ou CNPJ"""
    if not cpf_cnpj:
        return False
    numeros = re.sub(r'\D', '', cpf_cnpj)
    if len(numeros) not in [11, 14]:
        return False
    return True


def validar_email(email):
    """Valida formato básico de email"""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validar_placa(placa):
    """Valida formato de placa de veículo (Mercosul ou antiga)"""
    if not placa:
        return True  # Placa é opcional
    
    placa = placa.strip().upper()
    pattern_antiga = r'^[A-Z]{3}[0-9]{4}$'
    pattern_mercosul = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'
    placa_sem_hifen = placa.replace('-', '')
    
    return re.match(pattern_antiga, placa_sem_hifen) or re.match(pattern_mercosul, placa_sem_hifen)


def validar_uf(uf):
    """Valida UF brasileira"""
    if not uf:
        return True  # UF é opcional
    
    ufs_validas = [
        'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
        'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
        'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
    ]
    return uf.upper() in ufs_validas


# =============================================================================
# ROTAS DE CONFIGURAÇÃO
# =============================================================================

@admin_bp.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        tempo_cortesia_str = request.form.get('tempo_cortesia')
        max_passageiros_str = request.form.get('max_passageiros')

        config_cortesia = Configuracao.query.filter_by(
            chave='TEMPO_CORTESIA_MINUTOS').first()
        if not config_cortesia:
            config_cortesia = Configuracao(
                chave='TEMPO_CORTESIA_MINUTOS', valor=tempo_cortesia_str)
            db.session.add(config_cortesia)
        else:
            config_cortesia.valor = tempo_cortesia_str

        config_passageiros = Configuracao.query.filter_by(
            chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
        if not config_passageiros:
            config_passageiros = Configuracao(
                chave='MAX_PASSAGEIROS_POR_VIAGEM', valor=max_passageiros_str)
            db.session.add(config_passageiros)
        else:
            config_passageiros.valor = max_passageiros_str

        db.session.commit()
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('admin.configuracoes'))

    config_cortesia = Configuracao.query.filter_by(
        chave='TEMPO_CORTESIA_MINUTOS').first()
    config_passageiros = Configuracao.query.filter_by(
        chave='MAX_PASSAGEIROS_POR_VIAGEM').first()
    
    tempo_cortesia = config_cortesia.valor if config_cortesia else '30'
    max_passageiros = config_passageiros.valor if config_passageiros else '3'

    return render_template('configuracoes.html', 
                         tempo_cortesia=tempo_cortesia,
                         max_passageiros=max_passageiros)


# =============================================================================
# ROTA DE EXPORTAÇÃO CSV
# =============================================================================

@admin_bp.route('/admin/exportar_solicitacoes_csv')
@login_required
def exportar_solicitacoes_csv():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('admin.home'))

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

    output = StringIO()
    writer = csv.writer(output, delimiter=';')

    cabecalho = [
        'ID Viagem', 'ID Solicitacao', 'Status', 'Tipo Corrida', 'Data Chegada',
        'Colaborador', 'Planta', 'Bloco', 'Supervisor', 'Motorista',
        'Valor (R$)', 'Valor Repasse (R$)'
    ]
    writer.writerow(cabecalho)

    for solicitacao in solicitacoes_filtradas:
        bloco = solicitacao.colaborador.bloco
        linha = [
            solicitacao.viagem_id or '',
            solicitacao.id,
            solicitacao.status,
            solicitacao.tipo_corrida,
            solicitacao.horario_entrada.strftime('%d/%m/%Y %H:%M'),
            solicitacao.colaborador.nome,
            solicitacao.colaborador.planta.nome if solicitacao.colaborador.planta else '',
            bloco.codigo_bloco if bloco else '',
            solicitacao.supervisor.nome if solicitacao.supervisor else '',
            solicitacao.viagem.motorista.nome if solicitacao.viagem and solicitacao.viagem.motorista else '',
            f'{bloco.valor:.2f}' if bloco and bloco.valor else '0.00',
            f'{bloco.valor_repasse:.2f}' if bloco and bloco.valor_repasse else '0.00'
        ]
        writer.writerow(linha)

    csv_content = output.getvalue()
    nome_arquivo = f"solicitacoes_{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={nome_arquivo}"}
    )


# =============================================================================
# ROTAS DE IMPORTAÇÃO CSV - VERSÃO EXPANDIDA
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
    """
    Importação EXPANDIDA de colaboradores com TODOS os campos disponíveis.
    
    Formato CSV (separador: ponto e vírgula):
    matricula;nome;empresa;planta;email;telefone;endereco;nro;bairro;cidade;uf;bloco;status
    
    Campos obrigatórios: matricula, nome, empresa, planta
    Campos opcionais: email, telefone, endereco, nro, bairro, cidade, uf, bloco, status
    """
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

            colaboradores_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):
                if not any(field.strip() for field in row):
                    continue

                row = [field.strip() for field in row]

                # Valida número mínimo de campos (4 obrigatórios)
                if len(row) < 4:
                    erros.append(f"Linha {i}: Número insuficiente de campos (mínimo 4)")
                    linhas_ignoradas += 1
                    continue

                # Expande a lista para 13 campos (preenche com vazio se faltar)
                while len(row) < 13:
                    row.append('')

                # Desempacota TODOS os campos
                matricula, nome, empresa_nome, planta_nome, email, telefone, endereco, nro, bairro, cidade, uf, bloco_codigo, status = row[:13]

                # Validações obrigatórias
                if not matricula or not nome:
                    erros.append(f"Linha {i}: Matrícula e nome são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Verifica duplicidade de matrícula
                if Colaborador.query.filter_by(matricula=matricula).first():
                    erros.append(f"Linha {i}: Matrícula '{matricula}' já existe")
                    linhas_ignoradas += 1
                    continue

                # Valida email se fornecido
                if email and not validar_email(email):
                    erros.append(f"Linha {i}: E-mail '{email}' inválido")
                    linhas_ignoradas += 1
                    continue

                # Valida UF se fornecida
                if uf and not validar_uf(uf):
                    erros.append(f"Linha {i}: UF '{uf}' inválida")
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
                    erros.append(f"Linha {i}: Planta '{planta_nome}' não encontrada")
                    linhas_ignoradas += 1
                    continue

                # Busca bloco se fornecido
                bloco = None
                if bloco_codigo:
                    bloco = Bloco.query.filter_by(codigo_bloco=bloco_codigo, planta_id=planta.id).first()
                    if not bloco:
                        erros.append(f"Linha {i}: Bloco '{bloco_codigo}' não encontrado na planta '{planta_nome}'")
                        linhas_ignoradas += 1
                        continue

                # Valida status
                status_validos = ['Ativo', 'Inativo', 'Desligado', 'Ausente']
                if status and status not in status_validos:
                    status = 'Ativo'

                # Cria colaborador com TODOS os campos
                novo_colaborador = Colaborador(
                    matricula=matricula,
                    nome=nome,
                    empresa_id=empresa.id,
                    planta_id=planta.id,
                    email=email if email else None,
                    telefone=telefone if telefone else None,
                    endereco=endereco if endereco else None,
                    nro=nro if nro else None,
                    bairro=bairro if bairro else None,
                    cidade=cidade if cidade else None,
                    uf=uf.upper() if uf else None,
                    bloco_id=bloco.id if bloco else None,
                    status=status if status else 'Ativo'
                )
                db.session.add(novo_colaborador)
                colaboradores_adicionados += 1

            db.session.commit()

            # Mensagens de feedback
            if colaboradores_adicionados > 0:
                flash(f'{colaboradores_adicionados} colaboradores importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas.', 'warning')
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='colaboradores'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar arquivo: {e}', 'danger')
            return redirect(request.url)

    # GET: Busca dados para o template
    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.order_by(Planta.nome).all()
    blocos = Bloco.query.order_by(Bloco.codigo_bloco).all()
    
    return render_template('config/importar_colaboradores.html', 
                         empresas=empresas, 
                         plantas=plantas,
                         blocos=blocos)


@admin_bp.route('/importar_supervisores', methods=['GET', 'POST'])
@login_required
def importar_supervisores():
    """
    Importação EXPANDIDA de supervisores com TODOS os campos disponíveis.
    
    Formato CSV (separador: ponto e vírgula):
    matricula;nome;empresa;planta;gerente;email;senha;telefone;endereco;nro;bairro;cidade;uf;status
    
    Campos obrigatórios: matricula, nome, empresa, planta, gerente, email, senha
    Campos opcionais: telefone, endereco, nro, bairro, cidade, uf, status
    """
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

            next(csv_reader, None)

            supervisores_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):
                if not any(field.strip() for field in row):
                    continue

                row = [field.strip() for field in row]

                # Valida número mínimo de campos (7 obrigatórios)
                if len(row) < 7:
                    erros.append(f"Linha {i}: Número insuficiente de campos (mínimo 7)")
                    linhas_ignoradas += 1
                    continue

                # Expande para 14 campos
                while len(row) < 14:
                    row.append('')

                # Desempacota TODOS os campos
                matricula, nome, empresa_nome, planta_nome, gerente_matricula, email, senha, telefone, endereco, nro, bairro, cidade, uf, status = row[:14]

                # Validações obrigatórias
                if not all([matricula, nome, email, senha]):
                    erros.append(f"Linha {i}: Matrícula, nome, email e senha são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Valida email
                if not validar_email(email):
                    erros.append(f"Linha {i}: E-mail '{email}' inválido")
                    linhas_ignoradas += 1
                    continue

                # Valida senha
                if len(senha) < 6:
                    erros.append(f"Linha {i}: Senha deve ter no mínimo 6 caracteres")
                    linhas_ignoradas += 1
                    continue

                # Valida UF se fornecida
                if uf and not validar_uf(uf):
                    erros.append(f"Linha {i}: UF '{uf}' inválida")
                    linhas_ignoradas += 1
                    continue

                # Verifica duplicidade
                if Supervisor.query.filter_by(matricula=matricula).first():
                    erros.append(f"Linha {i}: Matrícula '{matricula}' já existe")
                    linhas_ignoradas += 1
                    continue

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
                    erros.append(f"Linha {i}: Planta '{planta_nome}' não encontrada")
                    linhas_ignoradas += 1
                    continue

                # Busca gerente
                gerente = Gerente.query.filter_by(matricula=gerente_matricula).first()
                if not gerente:
                    erros.append(f"Linha {i}: Gerente com matrícula '{gerente_matricula}' não encontrado")
                    linhas_ignoradas += 1
                    continue

                # Valida status
                status_validos = ['Ativo', 'Inativo', 'Desligado', 'Ausente']
                if status and status not in status_validos:
                    status = 'Ativo'

                # Cria usuário
                hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
                new_user = User(email=email, password=hashed_password, role='supervisor')
                db.session.add(new_user)
                db.session.flush()

                # Cria supervisor com TODOS os campos
                novo_supervisor = Supervisor(
                    user_id=new_user.id,
                    matricula=matricula,
                    nome=nome,
                    empresa_id=empresa.id,
                    planta_id=planta.id,
                    gerente_id=gerente.id,
                    email=email,
                    telefone=telefone if telefone else None,
                    endereco=endereco if endereco else None,
                    nro=nro if nro else None,
                    bairro=bairro if bairro else None,
                    cidade=cidade if cidade else None,
                    uf=uf.upper() if uf else None,
                    status=status if status else 'Ativo'
                )
                db.session.add(novo_supervisor)
                supervisores_adicionados += 1

            db.session.commit()

            if supervisores_adicionados > 0:
                flash(f'{supervisores_adicionados} supervisores importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas.', 'warning')
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='supervisores'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar arquivo: {e}', 'danger')
            return redirect(request.url)

    # GET
    empresas = Empresa.query.order_by(Empresa.nome).all()
    plantas = Planta.query.order_by(Planta.nome).all()
    gerentes = Gerente.query.order_by(Gerente.nome).all()
    
    return render_template('config/importar_supervisores.html', 
                         empresas=empresas, 
                         plantas=plantas,
                         gerentes=gerentes)


@admin_bp.route('/importar_motoristas', methods=['GET', 'POST'])
@login_required
def importar_motoristas():
    """
    Importação EXPANDIDA de motoristas com TODOS os campos disponíveis.
    
    Formato CSV (separador: ponto e vírgula):
    nome;cpf_cnpj;email;senha;telefone;endereco;nro;bairro;cidade;uf;chave_pix;veiculo_nome;veiculo_placa;veiculo_cor;veiculo_ano;veiculo_km;veiculo_obs;status
    
    Campos obrigatórios: nome, cpf_cnpj, email, senha
    Campos opcionais: todos os demais
    """
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

            next(csv_reader, None)

            motoristas_adicionados = 0
            linhas_ignoradas = 0
            erros = []

            for i, row in enumerate(csv_reader, 2):
                if not any(field.strip() for field in row):
                    continue

                row = [field.strip() for field in row]

                # Valida número mínimo de campos (4 obrigatórios)
                if len(row) < 4:
                    erros.append(f"Linha {i}: Número insuficiente de campos (mínimo 4)")
                    linhas_ignoradas += 1
                    continue

                # Expande para 18 campos
                while len(row) < 18:
                    row.append('')

                # Desempacota TODOS os campos
                (nome, cpf_cnpj, email, senha, telefone, endereco, nro, bairro, cidade, uf, 
                 chave_pix, veiculo_nome, veiculo_placa, veiculo_cor, veiculo_ano, 
                 veiculo_km, veiculo_obs, status) = row[:18]

                # Validações obrigatórias
                if not all([nome, cpf_cnpj, email, senha]):
                    erros.append(f"Linha {i}: Nome, CPF/CNPJ, email e senha são obrigatórios")
                    linhas_ignoradas += 1
                    continue

                # Valida CPF/CNPJ
                if not validar_cpf_cnpj(cpf_cnpj):
                    erros.append(f"Linha {i}: CPF/CNPJ '{cpf_cnpj}' inválido")
                    linhas_ignoradas += 1
                    continue

                # Valida email
                if not validar_email(email):
                    erros.append(f"Linha {i}: E-mail '{email}' inválido")
                    linhas_ignoradas += 1
                    continue

                # Valida senha
                if len(senha) < 6:
                    erros.append(f"Linha {i}: Senha deve ter no mínimo 6 caracteres")
                    linhas_ignoradas += 1
                    continue

                # Valida placa se fornecida
                if veiculo_placa and not validar_placa(veiculo_placa):
                    erros.append(f"Linha {i}: Placa '{veiculo_placa}' inválida")
                    linhas_ignoradas += 1
                    continue

                # Valida UF se fornecida
                if uf and not validar_uf(uf):
                    erros.append(f"Linha {i}: UF '{uf}' inválida")
                    linhas_ignoradas += 1
                    continue

                # Valida ano do veículo se fornecido
                veiculo_ano_int = None
                if veiculo_ano:
                    try:
                        veiculo_ano_int = int(veiculo_ano)
                        if veiculo_ano_int < 1900 or veiculo_ano_int > datetime.now().year + 1:
                            erros.append(f"Linha {i}: Ano do veículo '{veiculo_ano}' inválido")
                            linhas_ignoradas += 1
                            continue
                    except ValueError:
                        erros.append(f"Linha {i}: Ano do veículo deve ser um número")
                        linhas_ignoradas += 1
                        continue

                # Valida KM do veículo se fornecido
                veiculo_km_float = None
                if veiculo_km:
                    try:
                        veiculo_km_float = float(veiculo_km.replace(',', '.'))
                        if veiculo_km_float < 0:
                            erros.append(f"Linha {i}: KM do veículo não pode ser negativo")
                            linhas_ignoradas += 1
                            continue
                    except ValueError:
                        erros.append(f"Linha {i}: KM do veículo deve ser um número")
                        linhas_ignoradas += 1
                        continue

                # Verifica duplicidade
                if User.query.filter_by(email=email).first():
                    erros.append(f"Linha {i}: E-mail '{email}' já está em uso")
                    linhas_ignoradas += 1
                    continue

                if Motorista.query.filter_by(cpf_cnpj=cpf_cnpj).first():
                    erros.append(f"Linha {i}: CPF/CNPJ '{cpf_cnpj}' já cadastrado")
                    linhas_ignoradas += 1
                    continue

                if veiculo_placa and Motorista.query.filter_by(veiculo_placa=veiculo_placa.upper()).first():
                    erros.append(f"Linha {i}: Placa '{veiculo_placa}' já está em uso")
                    linhas_ignoradas += 1
                    continue

                # Valida status
                status_validos = ['Ativo', 'Inativo']
                if status and status not in status_validos:
                    status = 'Ativo'

                # Cria usuário
                hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
                new_user = User(email=email, password=hashed_password, role='motorista')
                db.session.add(new_user)
                db.session.flush()

                # Cria motorista com TODOS os campos
                novo_motorista = Motorista(
                    user_id=new_user.id,
                    nome=nome,
                    cpf_cnpj=cpf_cnpj,
                    email=email,
                    telefone=telefone if telefone else None,
                    endereco=endereco if endereco else None,
                    nro=nro if nro else None,
                    bairro=bairro if bairro else None,
                    cidade=cidade if cidade else None,
                    uf=uf.upper() if uf else None,
                    chave_pix=chave_pix if chave_pix else None,
                    veiculo_nome=veiculo_nome if veiculo_nome else None,
                    veiculo_placa=veiculo_placa.upper() if veiculo_placa else None,
                    veiculo_cor=veiculo_cor if veiculo_cor else None,
                    veiculo_ano=veiculo_ano_int,
                    veiculo_km=veiculo_km_float,
                    veiculo_obs=veiculo_obs if veiculo_obs else None,
                    status=status if status else 'Ativo',
                    status_disponibilidade='online'
                )
                db.session.add(novo_motorista)
                motoristas_adicionados += 1

            db.session.commit()

            if motoristas_adicionados > 0:
                flash(f'{motoristas_adicionados} motoristas importados com sucesso!', 'success')
            if linhas_ignoradas > 0:
                flash(f'{linhas_ignoradas} linhas foram ignoradas.', 'warning')
                for erro in erros[:5]:
                    flash(erro, 'info')
                if len(erros) > 5:
                    flash(f'... e mais {len(erros) - 5} erros.', 'info')

            return redirect(url_for('admin.admin_dashboard', aba='motoristas'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar arquivo: {e}', 'danger')
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
    
    query = Colaborador.query.filter(Colaborador.status == 'Ativo')
    
    if planta_id:
        query = query.filter(Colaborador.planta_id == planta_id)
    elif current_user.role == 'supervisor':
        query = query.filter(Colaborador.planta_id == current_user.supervisor.planta_id)
    
    query = query.filter(
        or_(
            Colaborador.nome.ilike(f'%{query_str}%'),
            Colaborador.matricula.ilike(f'%{query_str}%')
        )
    ).limit(10)
    
    colaboradores = query.all()
    
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

