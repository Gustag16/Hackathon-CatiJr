"""Envio de eventos para a sala (grupo do Channels).

NUNCA chame `send_to_room` direto de dentro de uma transação: use
`transaction.on_commit(lambda: send_to_room(...))`, para a sala só ver estado gravado (RF11).
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def room_group(auction_id) -> str:
    """Nome do grupo da sala. O consumer (Bortoleto) entra neste mesmo grupo."""
    return f"auction_{auction_id}"


def send_to_room(auction_id, message: dict) -> None:
    """`message` é o evento do contrato (seção 5), ex.: {"type": "bid_accepted", ...}.

    O consumer recebe em `room_event(self, event)` e repassa `event["message"]` ao navegador.
    """
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        room_group(auction_id), {"type": "room.event", "message": message}
    )
