#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Notificações por Email - Versão Simplificada
=======================================================

Este módulo gerencia o envio de notificações por email para eventos
relacionados a viagens (aceitação, cancelamento, finalização, etc.).

VERSÃO SIMPLIFICADA: Funciona SEM Flask-Mail instalado!
As notificações são logadas no console durante desenvolvimento.

Autor: Sistema DOUG Moving
Data: 2025
"""

from datetime import datetime


def init_mail(app):
    """
    Inicializa o sistema de notificações.
    
    Nota: Esta versão simplificada não requer Flask-Mail.
    """
    print("📧 Sistema de notificações inicializado (modo simulação)")


def enviar_email(destinatarios, assunto, corpo_html, corpo_texto=None):
    """
    Envia um email (modo simulação).
    
    Args:
        destinatarios: Lista de emails ou string com um email
        assunto: Assunto do email
        corpo_html: Corpo do email em HTML
        corpo_texto: Corpo do email em texto puro (opcional)
        
    Returns:
        bool: True (sempre, para não quebrar o fluxo)
    """
    # Garante que destinatarios seja uma lista
    if isinstance(destinatarios, str):
        destinatarios = [destinatarios]
    
    # Loga a notificação
    print(f"\n📧 [NOTIFICAÇÃO EMAIL]")
    print(f"   Para: {', '.join(destinatarios)}")
    print(f"   Assunto: {assunto}")
    print(f"   (Modo simulação - email não foi enviado)")
    
    return True


def notificar_viagem_aceita(viagem, email_supervisor):
    """
    Notifica o supervisor quando uma viagem é aceita por um motorista.
    
    Args:
        viagem: Objeto Viagem
        email_supervisor: Email do supervisor
    """
    assunto = f"Viagem Aceita - Viagem #{viagem.id}"
    
    corpo = f"""
    <h2>Viagem Aceita</h2>
    <p>A viagem #{viagem.id} foi aceita pelo motorista.</p>
    
    <h3>Detalhes da Viagem:</h3>
    <ul>
        <li><strong>Motorista:</strong> {viagem.nome_motorista}</li>
        <li><strong>Veículo:</strong> {viagem.placa_veiculo}</li>
        <li><strong>Passageiros:</strong> {viagem.quantidade_passageiros}</li>
        <li><strong>Tipo:</strong> {viagem.tipo_corrida}</li>
        <li><strong>Horário:</strong> {viagem.horario_entrada or viagem.horario_saida}</li>
    </ul>
    """
    
    return enviar_email(email_supervisor, assunto, corpo)


def notificar_viagem_cancelada(viagem, emails_destinatarios):
    """
    Notifica quando uma viagem é cancelada.
    
    Args:
        viagem: Objeto Viagem
        emails_destinatarios: Lista de emails para notificar
    """
    assunto = f"Viagem Cancelada - Viagem #{viagem.id}"
    
    corpo = f"""
    <h2>Viagem Cancelada</h2>
    <p>A viagem #{viagem.id} foi cancelada.</p>
    
    <h3>Detalhes:</h3>
    <ul>
        <li><strong>Motivo:</strong> {viagem.motivo_cancelamento}</li>
        <li><strong>Data do cancelamento:</strong> {viagem.data_cancelamento}</li>
        <li><strong>Motorista:</strong> {viagem.nome_motorista or 'Não atribuído'}</li>
    </ul>
    
    <p>As solicitações foram devolvidas para o status Pendente.</p>
    """
    
    return enviar_email(emails_destinatarios, assunto, corpo)


def notificar_viagem_finalizada(viagem, email_supervisor):
    """
    Notifica quando uma viagem é finalizada.
    
    Args:
        viagem: Objeto Viagem
        email_supervisor: Email do supervisor
    """
    assunto = f"Viagem Finalizada - Viagem #{viagem.id}"
    
    corpo = f"""
    <h2>Viagem Finalizada</h2>
    <p>A viagem #{viagem.id} foi finalizada com sucesso.</p>
    
    <h3>Resumo:</h3>
    <ul>
        <li><strong>Motorista:</strong> {viagem.nome_motorista}</li>
        <li><strong>Veículo:</strong> {viagem.placa_veiculo}</li>
        <li><strong>Passageiros:</strong> {viagem.quantidade_passageiros}</li>
        <li><strong>Valor da viagem:</strong> R$ {viagem.valor:.2f}</li>
        <li><strong>Valor de repasse:</strong> R$ {viagem.valor_repasse:.2f}</li>
        <li><strong>Data de finalização:</strong> {viagem.data_finalizacao}</li>
    </ul>
    """
    
    return enviar_email(email_supervisor, assunto, corpo)


# Template HTML para emails (versão completa)
TEMPLATE_EMAIL_BASE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #007bff;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 0 0 5px 5px;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 12px;
        }}
        ul {{
            list-style-type: none;
            padding: 0;
        }}
        li {{
            padding: 5px 0;
        }}
        strong {{
            color: #007bff;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>DOUG Moving</h1>
        <p>Sistema de Gestão de Transporte</p>
    </div>
    <div class="content">
        {conteudo}
    </div>
    <div class="footer">
        <p>Esta é uma notificação automática do sistema DOUG Moving.</p>
        <p>Por favor, não responda a este email.</p>
    </div>
</body>
</html>
"""

