# backend/auctions/consumers.py
import json
import uuid
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Auction


class AuctionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.accept()
            await self.close(code=4401)
            return

        raw_id = self.scope["url_route"]["kwargs"].get("auction_id")
        try:
            self.auction_id = str(uuid.UUID(str(raw_id)))
        except (ValueError, TypeError):
            await self.accept()
            await self.close(code=4404)
            return

        snapshot_payload = await self.get_auction_snapshot(self.auction_id)
        if snapshot_payload is None:
            await self.accept()
            await self.close(code=4404)
            return

        self.room_group_name = f"auction_{self.auction_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "snapshot",
            **snapshot_payload,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Canal somente leitura (lances entram via POST /api/auctions/{id}/bids)
        pass

    async def room_event(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def get_auction_snapshot(self, auction_id: str):
        try:
            auction = Auction.objects.select_related("seller", "winner").get(pk=auction_id)
        except Auction.DoesNotExist:
            return None

        # Ajuste os campos abaixo conforme o serializer já existente em auctions/
        bids = list(
            auction.bids.select_related("bidder")
            .order_by("-created_at")[:20]
            .values("id", "amount", "created_at", "bidder__username")
        )
        return {
            "auction": {
                "id": str(auction.id),
                "title": auction.title,
                "status": auction.status,
                "current_price": str(auction.current_price),
                "ends_at": auction.ends_at.isoformat() if auction.ends_at else None,
            },
            "bids": [
                {
                    "id": str(b["id"]),
                    "amount": str(b["amount"]),
                    "bidder": b["bidder__username"],
                    "created_at": b["created_at"].isoformat(),
                }
                for b in bids
            ],
        }