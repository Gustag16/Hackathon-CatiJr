"""Dados de demonstração (RNF04): 1 comitente, 3 compradores e ~100 leilões em todos os estados.

    python manage.py seed_demo           # cria só se ainda não existe (rodar 2x não duplica)
    python manage.py seed_demo --reset   # apaga os leilões de demonstração e recria

Os horários são relativos ao relógio do servidor no momento do comando. Use `--reset` pouco
antes da demo para ter leilões curtos abrindo e fechando na frente da banca.

Os leilões são gravados direto no banco já no estado final (é arranjo de dados, não uma
transição): nenhum lance passa por aqui em produção. Mesmo assim, os lances gerados respeitam
as regras de verdade (lance mínimo, ninguém cobre o próprio lance, comitente não dá lance).
"""

import io
import random
import textwrap
import unicodedata
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from accounts.models import User
from auctions.models import (
    Auction,
    AuctionParticipant,
    AuctionStatus,
    Bid,
    Item,
    ItemPhoto,
)
from auctions.rules.min_bid import increment_for, min_next_bid_cents
from auctions.services import clock

DEMO_PASSWORD = "leilao-demo-2026"
SELLER = ("comitente@demo.test", "Carlos Comitente")
BUYERS = [
    ("ana@demo.test", "Ana Compradora"),
    ("bruno@demo.test", "Bruno Comprador"),
    ("carla@demo.test", "Carla Compradora"),
]

# (categoria, nome, preço inicial em centavos)
CATALOG = [
    ("automoveis", "Fusca 1974 azul", 1_800_000),
    ("automoveis", "Bicicleta elétrica urbana", 450_000),
    ("automoveis", "Capacete de moto vintage", 35_000),
    ("automoveis", "Jogo de rodas aro 15", 120_000),
    ("moveis", "Poltrona de couro", 90_000),
    ("moveis", "Mesa de jantar de madeira maciça", 150_000),
    ("moveis", "Cadeira de escritório", 40_000),
    ("moveis", "Estante de ferro industrial", 60_000),
    ("eletronicos", "Notebook usado", 250_000),
    ("eletronicos", "Console de videogame", 180_000),
    ("eletronicos", "Fone de ouvido sem fio", 25_000),
    ("eletronicos", "Câmera fotográfica analógica", 70_000),
    ("eletronicos", "Rádio antigo a válvula", 30_000),
    ("arte", "Quadro a óleo de paisagem", 200_000),
    ("arte", "Escultura em pedra-sabão", 45_000),
    ("arte", "Gravura numerada", 80_000),
    ("hobbies-e-musica", "Violão de nylon", 55_000),
    ("hobbies-e-musica", "Teclado musical 61 teclas", 95_000),
    ("hobbies-e-musica", "Kit de pesca completo", 20_000),
    ("hobbies-e-musica", "Disco de vinil raro", 15_000),
    ("colecionaveis", "Moeda comemorativa de prata", 9_900),
    ("colecionaveis", "Álbum de figurinhas completo", 30_000),
    ("colecionaveis", "Selo postal antigo", 5_000),
    ("colecionaveis", "Miniatura de carro de corrida", 12_000),
    ("outros", "Relógio de bolso", 65_000),
    ("outros", "Mala de viagem de couro", 28_000),
    ("outros", "Máquina de costura antiga", 48_000),
]
CATEGORY_COLORS = {
    "automoveis": (52, 101, 164),
    "moveis": (143, 89, 2),
    "eletronicos": (40, 40, 60),
    "arte": (156, 39, 92),
    "hobbies-e-musica": (46, 125, 50),
    "colecionaveis": (191, 144, 0),
    "outros": (90, 90, 90),
}

# Quantos leilões de cada tipo (total 100). "curto" = abre/fecha em poucos minutos.
PLAN = [
    ("running", 20),
    ("running_short", 5),
    ("scheduled", 34),
    ("scheduled_short", 6),
    ("sold", 18),
    ("ended_no_bids", 9),
    ("cancelled", 8),
]

M = timedelta(minutes=1)
H = timedelta(hours=1)


class Command(BaseCommand):
    help = "Cria contas e ~100 leilões de demonstração (RNF04). Idempotente; --reset recria."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="apaga os leilões de demonstração e recria"
        )

    def handle(self, *args, reset: bool = False, **options):
        seller, buyers = self._accounts()
        if reset:
            removed = _delete_demo_auctions(seller)
            self.stdout.write(f"Removidos {removed} leilões de demonstração.")
        elif Item.objects.filter(seller=seller).exists():
            self.stdout.write("Dados de demonstração já existem (use --reset para recriar).")
            self._summary(seller)
            return
        _create_auctions(seller, buyers, random.Random(2026))
        self._summary(seller)

    def _accounts(self):
        def ensure(email, name):
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(email=email, display_name=name, password="x")
            user.set_password(DEMO_PASSWORD)  # garante a senha conhecida da demo
            user.save(update_fields=["password"])
            return user

        return ensure(*SELLER), [ensure(*b) for b in BUYERS]

    def _summary(self, seller):
        auctions = Auction.objects.filter(item__seller=seller)
        self.stdout.write(self.style.SUCCESS(f"{auctions.count()} leilões de demonstração:"))
        for status in AuctionStatus.values:
            self.stdout.write(f"  {status:<14} {auctions.filter(status=status).count()}")
        self.stdout.write(f"Contas (senha de todas: {DEMO_PASSWORD}):")
        for email, name in [SELLER, *BUYERS]:
            self.stdout.write(f"  {email:<22} {name}")


@transaction.atomic
def _delete_demo_auctions(seller) -> int:
    items = Item.objects.filter(seller=seller)
    auctions = Auction.objects.filter(item__in=items)
    count = auctions.count()
    Bid.objects.filter(auction__in=auctions).delete()
    auctions.update(leader=None)  # o líder protege o participante; solta antes de apagar
    AuctionParticipant.objects.filter(auction__in=auctions).delete()
    auctions.delete()
    for photo in ItemPhoto.objects.filter(item__in=items):
        photo.file.delete(save=False)  # apaga o arquivo do disco, não só a linha
    items.delete()
    return count


@transaction.atomic
def _create_auctions(seller, buyers, rng: random.Random) -> None:
    now = clock.now()
    number = 0
    for kind, amount in PLAN:
        for _ in range(amount):
            number += 1
            category, base_name, price = CATALOG[(number - 1) % len(CATALOG)]
            name = f"{base_name} (lote {number:03d})"
            starts_at, ends_at, status, bid_count = _timing(kind, now, rng)
            item = Item.objects.create(
                seller=seller,
                name=name,
                description=f"{base_name}. Item de demonstração; nenhuma transação é real.",
                category=category,
            )
            for index in range(3):
                ItemPhoto.objects.create(
                    item=item, file=_photo(name, category, index), position=index
                )
            auction = Auction.objects.create(
                item=item,
                status=status,
                start_price_cents=price,
                starts_at=starts_at,
                ends_at=ends_at,
                original_ends_at=ends_at,
            )
            if bid_count:
                _bids(auction, buyers, bid_count, min(now, ends_at), rng)


def _timing(kind: str, now, rng: random.Random):
    """(início, término, status, nº de lances) de cada tipo de leilão."""
    if kind == "running":
        starts_at = now - rng.randint(5, 180) * M
        ends_at = now + rng.randint(15, 600) * M
        return starts_at, ends_at, AuctionStatus.RUNNING, rng.choice([0, 0, 1, 2, 3, 5, 8])
    if kind == "running_short":  # fecham na frente da banca (3 a 10 min)
        starts_at = now - rng.randint(1, 5) * M
        ends_at = now + rng.randint(3, 10) * M
        return starts_at, ends_at, AuctionStatus.RUNNING, rng.choice([0, 1, 2])
    if kind == "scheduled":
        starts_at = now + rng.randint(10, 3 * 24 * 60) * M
        return starts_at, starts_at + rng.randint(30, 2 * 24 * 60) * M, AuctionStatus.SCHEDULED, 0
    if kind == "scheduled_short":  # abre em 1 a 5 min e dura 3 (o exemplo do RF06)
        starts_at = now + rng.randint(1, 5) * M
        return starts_at, starts_at + 3 * M, AuctionStatus.SCHEDULED, 0
    if kind == "sold":
        ends_at = now - rng.randint(1, 72) * H
        return ends_at - rng.randint(1, 24) * H, ends_at, AuctionStatus.SOLD, rng.randint(1, 10)
    if kind == "ended_no_bids":
        ends_at = now - rng.randint(1, 72) * H
        return ends_at - rng.randint(1, 24) * H, ends_at, AuctionStatus.ENDED_NO_BIDS, 0
    if kind == "cancelled":
        if rng.random() < 0.5:  # cancelado ainda agendado
            starts_at = now + rng.randint(30, 600) * M
        else:  # cancelado em andamento, sem lances
            starts_at = now - rng.randint(60, 600) * M
        return starts_at, starts_at + rng.randint(2, 48) * H, AuctionStatus.CANCELLED, 0
    raise ValueError(kind)


def _bids(auction: Auction, buyers, count: int, last_time, rng: random.Random) -> None:
    """Lances crescentes que respeitam o lance mínimo; ninguém cobre o próprio lance."""
    participants: dict = {}
    leader = None
    highest = None
    span = (last_time - auction.starts_at).total_seconds()
    times = sorted(
        auction.starts_at + timedelta(seconds=rng.uniform(1, span - 1)) for _ in range(count)
    )
    for created_at in times:
        user = rng.choice([b for b in buyers if leader is None or b.id != leader.user_id])
        if user.id not in participants:
            participants[user.id] = AuctionParticipant.objects.create(
                auction=auction, user=user, number=len(participants) + 1
            )
        minimum = min_next_bid_cents(
            start_price_cents=auction.start_price_cents, highest_bid_cents=highest
        )
        amount = minimum + rng.choice([0, 0, 1, 2]) * increment_for(minimum)
        leader = participants[user.id]
        Bid.objects.create(
            auction=auction, participant=leader, amount_cents=amount, created_at=created_at
        )
        highest = amount
    auction.highest_bid_cents = highest
    auction.leader = leader
    auction.bid_count = count
    auction.save(update_fields=["highest_bid_cents", "leader", "bid_count"])


def _ascii(text: str) -> str:
    """A fonte embutida do Pillow não tem acentos ("Relógio" sairia com um quadrado)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _photo(name: str, category: str, index: int) -> ContentFile:
    """JPEG pequeno gerado na hora: cor da categoria, nome do item e número da foto."""
    red, green, blue = CATEGORY_COLORS[category]
    image = Image.new("RGB", (480, 360))
    draw = ImageDraw.Draw(image)
    for y in range(360):  # degradê vertical, um pouco diferente em cada foto
        shade = 1 - y / 720 - index * 0.08
        draw.line(
            [(0, y), (480, y)], fill=(int(red * shade), int(green * shade), int(blue * shade))
        )
    try:
        font, small = ImageFont.load_default(size=26), ImageFont.load_default(size=18)
    except TypeError:  # Pillow antigo
        font = small = ImageFont.load_default()
    draw.multiline_text((24, 130), textwrap.fill(_ascii(name), 30), fill="white", font=font)
    draw.text((24, 310), f"Foto {index + 1}/3 - demonstracao", fill=(230, 230, 230), font=small)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return ContentFile(buffer.getvalue(), name="foto.jpg")
