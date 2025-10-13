"""
Pacote de utilitários do sistema DOUG Moving
"""

from .notificacoes import (
    init_mail,
    enviar_email,
    notificar_viagem_aceita,
    notificar_viagem_cancelada,
    notificar_viagem_finalizada
)

__all__ = [
    'init_mail',
    'enviar_email',
    'notificar_viagem_aceita',
    'notificar_viagem_cancelada',
    'notificar_viagem_finalizada'
]

