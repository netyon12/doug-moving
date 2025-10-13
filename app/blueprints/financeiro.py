"""
Blueprint do Módulo Financeiro
Gerenciamento de Contas a Receber e Contas a Pagar
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    FinContasReceber, FinReceberViagens,
    FinContasPagar, FinPagarViagens,
    Viagem, Empresa, Motorista, User
)
from app.decorators import permission_required
from datetime import datetime, date
from sqlalchemy import and_, or_

financeiro_bp = Blueprint('financeiro', __name__, url_prefix='/admin/financeiro')


# ===========================================================================================
# CONTAS A RECEBER
# ===========================================================================================

@financeiro_bp.route('/contas-receber')
@login_required
@permission_required(['admin'])
def contas_receber():
    """Lista todos os títulos a receber"""
    
    # Filtros
    filtro_status = request.args.get('status', '')
    filtro_empresa_id = request.args.get('empresa_id', '')
    filtro_data_inicio = request.args.get('data_inicio', '')
    filtro_data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = FinContasReceber.query
    
    # Aplicar filtros
    if filtro_status:
        query = query.filter(FinContasReceber.status == filtro_status)
    
    if filtro_empresa_id:
        query = query.filter(FinContasReceber.empresa_id == int(filtro_empresa_id))
    
    if filtro_data_inicio:
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date()
        query = query.filter(FinContasReceber.data_emissao >= data_inicio)
    
    if filtro_data_fim:
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date()
        query = query.filter(FinContasReceber.data_emissao <= data_fim)
    
    # Ordenar por data de emissão decrescente
    titulos = query.order_by(FinContasReceber.data_emissao.desc()).all()
    
    # Buscar empresas para o filtro
    empresas = Empresa.query.filter_by(status='Ativo').order_by(Empresa.nome).all()
    
    # Calcular totalizadores
    total_aberto = sum([float(t.valor_total) for t in titulos if t.status == 'Aberto'])
    total_recebido = sum([float(t.valor_total) for t in titulos if t.status == 'Recebido'])
    total_vencido = sum([float(t.valor_total) for t in titulos if t.status == 'Vencido'])
    
    return render_template('financeiro/contas_receber.html',
                         titulos=titulos,
                         empresas=empresas,
                         filtro_status=filtro_status,
                         filtro_empresa_id=filtro_empresa_id,
                         filtro_data_inicio=filtro_data_inicio,
                         filtro_data_fim=filtro_data_fim,
                         total_aberto=total_aberto,
                         total_recebido=total_recebido,
                         total_vencido=total_vencido)


@financeiro_bp.route('/gerar-fatura', methods=['GET', 'POST'])
@login_required
@permission_required(['admin'])
def gerar_fatura():
    """Tela para gerar nova fatura a receber"""
    
    if request.method == 'POST':
        # Processar geração da fatura
        empresa_id = request.form.get('empresa_id')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        viagens_ids = request.form.getlist('viagens_ids')
        data_vencimento = request.form.get('data_vencimento')
        
        if not all([empresa_id, data_inicio, data_fim, viagens_ids, data_vencimento]):
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('financeiro.gerar_fatura'))
        
        try:
            # Buscar viagens selecionadas
            viagens = Viagem.query.filter(Viagem.id.in_(viagens_ids)).all()
            
            if not viagens:
                flash('Nenhuma viagem selecionada!', 'danger')
                return redirect(url_for('financeiro.gerar_fatura'))
            
            # Calcular valor total
            valor_total = sum([float(v.valor) for v in viagens])
            
            # Gerar número do título
            ultimo_titulo = FinContasReceber.query.order_by(FinContasReceber.id.desc()).first()
            if ultimo_titulo:
                ultimo_numero = int(ultimo_titulo.numero_titulo.split('-')[-1])
                novo_numero = f"REC-{date.today().year}-{str(ultimo_numero + 1).zfill(4)}"
            else:
                novo_numero = f"REC-{date.today().year}-0001"
            
            # Criar título a receber
            titulo = FinContasReceber(
                numero_titulo=novo_numero,
                empresa_id=int(empresa_id),
                valor_total=valor_total,
                data_emissao=date.today(),
                data_vencimento=datetime.strptime(data_vencimento, '%Y-%m-%d').date(),
                status='Aberto',
                created_by_user_id=current_user.id
            )
            
            db.session.add(titulo)
            db.session.flush()  # Para obter o ID do título
            
            # Vincular viagens ao título
            for viagem in viagens:
                vinculo = FinReceberViagens(
                    conta_receber_id=titulo.id,
                    viagem_id=viagem.id,
                    valor_viagem=float(viagem.valor)
                )
                db.session.add(vinculo)
            
            db.session.commit()
            
            flash(f'Título {novo_numero} gerado com sucesso! Valor total: R$ {valor_total:.2f}', 'success')
            return redirect(url_for('financeiro.editar_receber', titulo_id=titulo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao gerar título: {str(e)}', 'danger')
            return redirect(url_for('financeiro.gerar_fatura'))
    
    # GET - Exibir formulário
    empresas = Empresa.query.filter_by(status='Ativo').order_by(Empresa.nome).all()
    return render_template('financeiro/gerar_fatura.html', empresas=empresas)


@financeiro_bp.route('/buscar-viagens-receber', methods=['POST'])
@login_required
@permission_required(['admin'])
def buscar_viagens_receber():
    """API para buscar viagens finalizadas para faturamento"""
    
    empresa_id = request.json.get('empresa_id')
    data_inicio = request.json.get('data_inicio')
    data_fim = request.json.get('data_fim')
    
    if not all([empresa_id, data_inicio, data_fim]):
        return jsonify({'success': False, 'message': 'Parâmetros incompletos'}), 400
    
    try:
        # Converter datas
        dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
        
        # Buscar viagens finalizadas que ainda não foram faturadas
        viagens_faturadas_ids = db.session.query(FinReceberViagens.viagem_id).all()
        viagens_faturadas_ids = [v[0] for v in viagens_faturadas_ids]
        
        viagens = Viagem.query.filter(
            and_(
                Viagem.empresa_id == int(empresa_id),
                Viagem.status == 'Finalizada',
                Viagem.data_criacao >= dt_inicio,
                Viagem.data_criacao <= dt_fim,
                ~Viagem.id.in_(viagens_faturadas_ids) if viagens_faturadas_ids else True
            )
        ).order_by(Viagem.data_criacao.desc()).all()
        
        # Montar resposta
        viagens_data = []
        valor_total = 0
        
        for v in viagens:
            viagens_data.append({
                'id': v.id,
                'data': v.data_criacao.strftime('%d/%m/%Y %H:%M') if v.data_criacao else 'N/A',
                'tipo': v.tipo_corrida,
                'passageiros': v.quantidade_passageiros,
                'valor': float(v.valor) if v.valor else 0.0,
                'bloco': v.bloco.codigo_bloco if v.bloco else 'N/A',
                'motorista': v.motorista.nome if v.motorista else 'Não atribuído'
            })
            valor_total += float(v.valor) if v.valor else 0.0
        
        return jsonify({
            'success': True,
            'viagens': viagens_data,
            'total_viagens': len(viagens_data),
            'valor_total': valor_total
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@financeiro_bp.route('/editar-receber/<int:titulo_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin'])
def editar_receber(titulo_id):
    """Editar título a receber"""
    
    titulo = FinContasReceber.query.get_or_404(titulo_id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados
            titulo.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date()
            titulo.numero_nota_fiscal = request.form.get('numero_nota_fiscal')
            titulo.observacoes = request.form.get('observacoes')
            
            # Atualizar status se recebido
            if request.form.get('status') == 'Recebido':
                titulo.status = 'Recebido'
                titulo.data_recebimento = datetime.strptime(request.form.get('data_recebimento'), '%Y-%m-%d').date()
            
            titulo.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Título atualizado com sucesso!', 'success')
            return redirect(url_for('financeiro.contas_receber'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar título: {str(e)}', 'danger')
    
    # Buscar viagens vinculadas
    viagens_vinculadas = db.session.query(Viagem, FinReceberViagens).join(
        FinReceberViagens, Viagem.id == FinReceberViagens.viagem_id
    ).filter(FinReceberViagens.conta_receber_id == titulo_id).all()
    
    return render_template('financeiro/editar_receber.html', 
                         titulo=titulo,
                         viagens_vinculadas=viagens_vinculadas)


@financeiro_bp.route('/excluir-receber/<int:titulo_id>', methods=['POST'])
@login_required
@permission_required(['admin'])
def excluir_receber(titulo_id):
    """Excluir título a receber"""
    
    titulo = FinContasReceber.query.get_or_404(titulo_id)
    
    # Não permitir excluir títulos recebidos
    if titulo.status == 'Recebido':
        flash('Não é possível excluir um título já recebido!', 'danger')
        return redirect(url_for('financeiro.contas_receber'))
    
    try:
        db.session.delete(titulo)
        db.session.commit()
        flash(f'Título {titulo.numero_titulo} excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir título: {str(e)}', 'danger')
    
    return redirect(url_for('financeiro.contas_receber'))


# ===========================================================================================
# CONTAS A PAGAR
# ===========================================================================================

@financeiro_bp.route('/contas-pagar')
@login_required
@permission_required(['admin'])
def contas_pagar():
    """Lista todos os títulos a pagar"""
    
    # Filtros
    filtro_status = request.args.get('status', '')
    filtro_motorista_id = request.args.get('motorista_id', '')
    filtro_data_inicio = request.args.get('data_inicio', '')
    filtro_data_fim = request.args.get('data_fim', '')
    
    # Query base
    query = FinContasPagar.query
    
    # Aplicar filtros
    if filtro_status:
        query = query.filter(FinContasPagar.status == filtro_status)
    
    if filtro_motorista_id:
        query = query.filter(FinContasPagar.motorista_id == int(filtro_motorista_id))
    
    if filtro_data_inicio:
        data_inicio = datetime.strptime(filtro_data_inicio, '%Y-%m-%d').date()
        query = query.filter(FinContasPagar.data_emissao >= data_inicio)
    
    if filtro_data_fim:
        data_fim = datetime.strptime(filtro_data_fim, '%Y-%m-%d').date()
        query = query.filter(FinContasPagar.data_emissao <= data_fim)
    
    # Ordenar por data de emissão decrescente
    titulos = query.order_by(FinContasPagar.data_emissao.desc()).all()
    
    # Buscar motoristas para o filtro
    motoristas = Motorista.query.filter_by(status='Ativo').order_by(Motorista.nome).all()
    
    # Calcular totalizadores
    total_aberto = sum([float(t.valor_total) for t in titulos if t.status == 'Aberto'])
    total_pago = sum([float(t.valor_total) for t in titulos if t.status == 'Pago'])
    total_vencido = sum([float(t.valor_total) for t in titulos if t.status == 'Vencido'])
    
    return render_template('financeiro/contas_pagar.html',
                         titulos=titulos,
                         motoristas=motoristas,
                         filtro_status=filtro_status,
                         filtro_motorista_id=filtro_motorista_id,
                         filtro_data_inicio=filtro_data_inicio,
                         filtro_data_fim=filtro_data_fim,
                         total_aberto=total_aberto,
                         total_pago=total_pago,
                         total_vencido=total_vencido)


@financeiro_bp.route('/gerar-pagamento', methods=['GET', 'POST'])
@login_required
@permission_required(['admin'])
def gerar_pagamento():
    """Tela para gerar novo pagamento a motorista"""
    
    if request.method == 'POST':
        # Processar geração do pagamento
        motorista_id = request.form.get('motorista_id')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        viagens_ids = request.form.getlist('viagens_ids')
        data_vencimento = request.form.get('data_vencimento')
        
        if not all([motorista_id, data_inicio, data_fim, viagens_ids, data_vencimento]):
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('financeiro.gerar_pagamento'))
        
        try:
            # Buscar viagens selecionadas
            viagens = Viagem.query.filter(Viagem.id.in_(viagens_ids)).all()
            
            if not viagens:
                flash('Nenhuma viagem selecionada!', 'danger')
                return redirect(url_for('financeiro.gerar_pagamento'))
            
            # Calcular valor total (repasse)
            valor_total = sum([float(v.valor_repasse) for v in viagens if v.valor_repasse])
            
            # Gerar número do título
            ultimo_titulo = FinContasPagar.query.order_by(FinContasPagar.id.desc()).first()
            if ultimo_titulo:
                ultimo_numero = int(ultimo_titulo.numero_titulo.split('-')[-1])
                novo_numero = f"PAG-{date.today().year}-{str(ultimo_numero + 1).zfill(4)}"
            else:
                novo_numero = f"PAG-{date.today().year}-0001"
            
            # Criar título a pagar
            titulo = FinContasPagar(
                numero_titulo=novo_numero,
                motorista_id=int(motorista_id),
                valor_total=valor_total,
                data_emissao=date.today(),
                data_vencimento=datetime.strptime(data_vencimento, '%Y-%m-%d').date(),
                status='Aberto',
                created_by_user_id=current_user.id
            )
            
            db.session.add(titulo)
            db.session.flush()  # Para obter o ID do título
            
            # Vincular viagens ao título
            for viagem in viagens:
                vinculo = FinPagarViagens(
                    conta_pagar_id=titulo.id,
                    viagem_id=viagem.id,
                    valor_repasse=float(viagem.valor_repasse) if viagem.valor_repasse else 0.0
                )
                db.session.add(vinculo)
            
            db.session.commit()
            
            flash(f'Título {novo_numero} gerado com sucesso! Valor total: R$ {valor_total:.2f}', 'success')
            return redirect(url_for('financeiro.editar_pagar', titulo_id=titulo.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao gerar título: {str(e)}', 'danger')
            return redirect(url_for('financeiro.gerar_pagamento'))
    
    # GET - Exibir formulário
    motoristas = Motorista.query.filter_by(status='Ativo').order_by(Motorista.nome).all()
    return render_template('financeiro/gerar_pagamento.html', motoristas=motoristas)


@financeiro_bp.route('/buscar-viagens-pagar', methods=['POST'])
@login_required
@permission_required(['admin'])
def buscar_viagens_pagar():
    """API para buscar viagens finalizadas para pagamento"""
    
    motorista_id = request.json.get('motorista_id')
    data_inicio = request.json.get('data_inicio')
    data_fim = request.json.get('data_fim')
    
    if not all([motorista_id, data_inicio, data_fim]):
        return jsonify({'success': False, 'message': 'Parâmetros incompletos'}), 400
    
    try:
        # Converter datas
        dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d')
        
        # Buscar viagens finalizadas que ainda não foram pagas
        viagens_pagas_ids = db.session.query(FinPagarViagens.viagem_id).all()
        viagens_pagas_ids = [v[0] for v in viagens_pagas_ids]
        
        viagens = Viagem.query.filter(
            and_(
                Viagem.motorista_id == int(motorista_id),
                Viagem.status == 'Finalizada',
                Viagem.data_criacao >= dt_inicio,
                Viagem.data_criacao <= dt_fim,
                ~Viagem.id.in_(viagens_pagas_ids) if viagens_pagas_ids else True
            )
        ).order_by(Viagem.data_criacao.desc()).all()
        
        # Montar resposta
        viagens_data = []
        valor_total = 0
        
        for v in viagens:
            valor_repasse = float(v.valor_repasse) if v.valor_repasse else 0.0
            viagens_data.append({
                'id': v.id,
                'data': v.data_criacao.strftime('%d/%m/%Y %H:%M') if v.data_criacao else 'N/A',
                'tipo': v.tipo_corrida,
                'passageiros': v.quantidade_passageiros,
                'valor_repasse': valor_repasse,
                'bloco': v.bloco.codigo_bloco if v.bloco else 'N/A'
            })
            valor_total += valor_repasse
        
        return jsonify({
            'success': True,
            'viagens': viagens_data,
            'total_viagens': len(viagens_data),
            'valor_total': valor_total
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@financeiro_bp.route('/editar-pagar/<int:titulo_id>', methods=['GET', 'POST'])
@login_required
@permission_required(['admin'])
def editar_pagar(titulo_id):
    """Editar título a pagar"""
    
    titulo = FinContasPagar.query.get_or_404(titulo_id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados
            titulo.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date()
            titulo.forma_pagamento = request.form.get('forma_pagamento')
            titulo.observacoes = request.form.get('observacoes')
            
            # Atualizar status se pago
            if request.form.get('status') == 'Pago':
                titulo.status = 'Pago'
                titulo.data_pagamento = datetime.strptime(request.form.get('data_pagamento'), '%Y-%m-%d').date()
            
            titulo.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Título atualizado com sucesso!', 'success')
            return redirect(url_for('financeiro.contas_pagar'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar título: {str(e)}', 'danger')
    
    # Buscar viagens vinculadas
    viagens_vinculadas = db.session.query(Viagem, FinPagarViagens).join(
        FinPagarViagens, Viagem.id == FinPagarViagens.viagem_id
    ).filter(FinPagarViagens.conta_pagar_id == titulo_id).all()
    
    return render_template('financeiro/editar_pagar.html', 
                         titulo=titulo,
                         viagens_vinculadas=viagens_vinculadas)


@financeiro_bp.route('/excluir-pagar/<int:titulo_id>', methods=['POST'])
@login_required
@permission_required(['admin'])
def excluir_pagar(titulo_id):
    """Excluir título a pagar"""
    
    titulo = FinContasPagar.query.get_or_404(titulo_id)
    
    # Não permitir excluir títulos pagos
    if titulo.status == 'Pago':
        flash('Não é possível excluir um título já pago!', 'danger')
        return redirect(url_for('financeiro.contas_pagar'))
    
    try:
        db.session.delete(titulo)
        db.session.commit()
        flash(f'Título {titulo.numero_titulo} excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir título: {str(e)}', 'danger')
    
    return redirect(url_for('financeiro.contas_pagar'))

