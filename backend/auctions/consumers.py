"""WebSocket da sala do leilão (contrato, seção 5). URL: `/ws/auctions/{id}/`.

O consumer só TRANSMITE estado: lances entram por POST HTTP. Ele nunca monta JSON de leilão
por conta própria; o `snapshot` vem de `services.room.room_snapshot` e os eventos chegam
prontos do backend pelo grupo `auction_<uuid>` (ver `services/broadcast.py`). Assim o id do
líder nunca vaza: só `leader_number` e `leader_label`.
"""

import json
import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Auction
from .serializers import iso_z
from .services import clock
from .services.broadcast import room_group
from .services.room import room_snapshot

CLOSE_NOT_AUTHENTICATED = 4401
CLOSE_NOT_FOUND = 4404


class AuctionConsumer(AsyncWebsocketConsumer):
    group: str | None = None  # só existe depois de entrar na sala

    async def connect(self):
        # Aceitamos ANTES de fechar: só assim o navegador recebe o código 4401/4404
        # (recusar no handshake vira um erro genérico, sem código).
        await self.accept()

        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=CLOSE_NOT_AUTHENTICATED)
            return
        try:
            auction_id = uuid.UUID(str(self.scope["url_route"]["kwargs"]["auction_id"]))
        except ValueError:
            await self.close(code=CLOSE_NOT_FOUND)
            return

        self.user = user
        self.auction_id = auction_id
        # Entra no grupo ANTES de ler o snapshot: um lance gravado entre as duas coisas
        # fica na fila e chega logo depois do snapshot, em vez de se perder.
        self.group = room_group(auction_id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self._send_snapshot()

    async def disconnect(self, close_code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)
            self.group = None

    async def receive(self, text_data=None, bytes_data=None):
        """Cliente -> servidor: `resync` e `ping`. Mensagem ruim leva `error`, sem derrubar."""
        if self.group is None:
            return  # conexão recusada (4401/4404) que ainda mandou algo: ignora
        try:
            message = json.loads(text_data or "")
        except ValueError:
            await self._send_error("INVALID_MESSAGE", "Envie um objeto JSON com o campo type.")
            return
        kind = message.get("type") if isinstance(message, dict) else None
        if kind == "resync":
            await self._send_snapshot()
        elif kind == "ping":
            await self._send({"type": "pong", "server_time": iso_z(clock.now())})
        elif isinstance(kind, str):
            await self._send_error("UNKNOWN_TYPE", "Tipo de mensagem desconhecido.")
        else:
            await self._send_error("INVALID_MESSAGE", "Envie um objeto JSON com o campo type.")

    async def room_event(self, event):
        """Evento publicado pelo backend depois do commit: repassa como veio."""
        await self._send(event["message"])

    async def _send_snapshot(self):
        try:
            snapshot = await database_sync_to_async(room_snapshot)(self.auction_id, self.user)
        except Auction.DoesNotExist:
            await self.channel_layer.group_discard(self.group, self.channel_name)
            self.group = None
            await self.close(code=CLOSE_NOT_FOUND)
            return
        await self._send(snapshot)

    async def _send_error(self, code: str, message: str):
        await self._send(
            {"type": "error", "code": code, "message": message, "server_time": iso_z(clock.now())}
        )

    async def _send(self, payload: dict):
        await self.send(text_data=json.dumps(payload))
