"""
Configuração de Logging para Produção (Render) e Desenvolvimento

Este módulo configura o sistema de logging do Flask para funcionar
corretamente tanto em ambiente local quanto em produção no Render.

Autor: Manus AI
Data: 06 de Novembro de 2025
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
import os


def setup_logging(app):
    """
    Configura logging para funcionar tanto local quanto em produção
    
    Em produção (Render):
    - Logs vão para stdout (aparecem no painel Logs do Render)
    - Nível INFO (menos verboso)
    
    Em desenvolvimento (local):
    - Logs vão para stdout E arquivo (logs/app.log)
    - Nível DEBUG (mais verboso)
    
    Args:
        app: Instância do Flask
        
    Returns:
        app: Instância do Flask com logging configurado
    """
    
    # Remove handlers existentes para evitar duplicação
    app.logger.handlers.clear()
    
    # Determina ambiente
    is_production = (
        os.getenv('FLASK_ENV') == 'production' or 
        os.getenv('RENDER') == 'true' or
        os.getenv('RENDER_SERVICE_NAME') is not None
    )
    
    # Define nível de log baseado no ambiente
    if is_production:
        log_level = logging.INFO
        env_name = 'PRODUÇÃO (Render)'
    else:
        log_level = logging.DEBUG
        env_name = 'DESENVOLVIMENTO (Local)'
    
    app.logger.setLevel(log_level)
    
    # ===== HANDLER 1: Console (stdout) - ESSENCIAL PARA RENDER =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Formato limpo para console (sem pathname/lineno)
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    app.logger.addHandler(console_handler)
    
    # ===== HANDLER 2: Arquivo (apenas local) =====
    if not is_production:
        try:
            # Criar diretório de logs se não existir
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            # Handler de arquivo com rotação
            file_handler = RotatingFileHandler(
                'logs/app.log',
                maxBytes=10485760,  # 10MB
                backupCount=10
            )
            file_handler.setLevel(logging.DEBUG)
            
            # Formato mais detalhado para arquivo
            file_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            
            app.logger.addHandler(file_handler)
        except Exception as e:
            app.logger.warning(f"[AVISO]  Não foi possível criar handler de arquivo: {e}")
    
    # ===== Configurar logger raiz =====
    # Isso garante que outros módulos também loguem corretamente
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove handlers existentes do root logger
    root_logger.handlers.clear()
    
    # Adiciona console handler ao root logger
    root_logger.addHandler(console_handler)
    
    # ===== Reduzir verbosidade de bibliotecas externas =====
    # Gunicorn (servidor web)
    logging.getLogger('gunicorn.access').setLevel(logging.WARNING)
    logging.getLogger('gunicorn.error').setLevel(logging.ERROR)
    
    # Werkzeug (servidor de desenvolvimento do Flask)
    # ERROR para evitar tracebacks internos no terminal
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    # SQLAlchemy (apenas em produção)
    if is_production:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # ===== Logs iniciais =====
    app.logger.info("="*70)
    app.logger.info(f"[START] Sistema de Logging Configurado")
    app.logger.info(f"[STATS] Ambiente: {env_name}")
    app.logger.info(f"📈 Nível de log: {logging.getLevelName(log_level)}")
    
    if is_production:
        app.logger.info("[>>>] Logs sendo enviados para: stdout (Render Logs)")
    else:
        app.logger.info("[>>>] Logs sendo enviados para: stdout + logs/app.log")
    
    app.logger.info("="*70)
    
    # ===== Silenciar tracebacks internos do Python =====
    import threading
    
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        """Hook personalizado para capturar exceções não tratadas"""
        # Ignora KeyboardInterrupt (Ctrl+C)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Loga apenas a mensagem de erro, sem traceback completo
        app.logger.error(f"[ERRO] Exceção não tratada: {exc_type.__name__}: {exc_value}")
    
    def custom_threading_excepthook(args):
        """Hook personalizado para threads"""
        app.logger.error(f"[ERRO] Exceção em thread: {args.exc_type.__name__}: {args.exc_value}")
    
    # Aplica hooks apenas em produção
    if is_production:
        sys.excepthook = custom_excepthook
        threading.excepthook = custom_threading_excepthook
    
    return app


def get_logger(name):
    """
    Retorna um logger configurado para um módulo específico
    
    Uso:
        from app.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Mensagem de log")
    
    Args:
        name: Nome do módulo (use __name__)
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
