"""Envio de eventos para a sala (grupo do Channels). Contrato, seção 5 ("Ponte").

Regra de ouro (RF11): a sala só vê estado GRAVADO. Por isso o código de negócio chama
`announce_after_commit`, que agenda o envio com `transaction.on_commit`: se a transação
fizer rollback, nada é enviado; se fizer commit, o envio acontece logo depois.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from auctions.serializers import jsonable

logger = logging.getLogger(__name__)


def room_group(auction_id) -> str:
    """Nome do grupo da sala. O consumer (Bortoleto) entra neste mesmo grupo."""
    return f"auction_{auction_id}"


def send_to_room(auction_id, message: dict) -> None:
    """Envia AGORA. Não chame de dentro de uma transação: use `announce_after_commit`.

    O consumer recebe em `room_event(self, event)` e repassa `event["message"]` ao navegador.
    """
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        room_group(auction_id), {"type": "room.event", "message": message}
    )


def announce_after_commit(auction_id, message: dict) -> None:
    """Agenda o evento para depois do COMMIT da transação atual.

    `message` é montada AGORA (com o estado que está sendo gravado) e convertida para JSON
    puro, porque o Redis não transporta objetos datetime/UUID.
    """
    payload = jsonable(message)

    def _send():
        try:
            send_to_room(auction_id, payload)
        except Exception:
            # O lance JÁ foi gravado: uma falha do Redis não pode virar erro para quem deu o
            # lance. A sala se corrige no próximo evento ou no `snapshot` ao reconectar.
            logger.exception("falha ao avisar a sala %s (%s)", auction_id, payload.get("type"))

    transaction.on_commit(_send)
