"""Item 4 da etapa 1: seed_demo (RNF04)."""

import io
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.management import call_command

from accounts.models import User
from auctions.models import Auction, Bid, ItemPhoto
from auctions.rules.min_bid import min_next_bid_cents

pytestmark = pytest.mark.django_db

EMAILS = {"comitente@demo.test", "ana@demo.test", "bruno@demo.test", "carla@demo.test"}


@pytest.fixture
def seeded(media, clock):
    call_command("seed_demo", stdout=io.StringIO())
    return clock.now


def test_contas_de_demonstracao(seeded, api):
    assert set(User.objects.values_list("email", flat=True)) == EMAILS
    response = api.post(
        "/api/auth/login",
        {"email": "ana@demo.test", "password": "leilao-demo-2026"},
        format="json",
    )
    assert response.status_code == 200


def test_cem_leiloes_em_todos_os_estados(seeded):
    counts = Counter(Auction.objects.values_list("status", flat=True))
    assert sum(counts.values()) == 100
    assert set(counts) == {"scheduled", "running", "sold", "ended_no_bids", "cancelled"}
    sellers = set(Auction.objects.values_list("item__seller__email", flat=True))
    assert sellers == {"comitente@demo.test"}


def test_cada_item_tem_3_fotos_no_disco(seeded, media):
    for auction in Auction.objects.select_related("item"):
        photos = list(auction.item.photos.all())
        assert len(photos) >= 3
        for photo in photos:
            path = Path(photo.file.path)
            assert path.is_file() and path.suffix == ".jpg" and media in path.parents


def test_itens_mapeados_usam_a_foto_real(seeded):
    from auctions.management.commands.seed_demo import REAL_PHOTOS, SEED_PHOTOS_DIR

    assert len(REAL_PHOTOS) == 26
    for base_name, filename in REAL_PHOTOS.items():
        original = (SEED_PHOTOS_DIR / filename).read_bytes()
        assert original[:3] == b"\xff\xd8\xff"  # JPEG pelo conteúdo
        photos = ItemPhoto.objects.filter(item__name__startswith=f"{base_name} (lote")
        assert photos.count() >= 3
        for photo in photos:
            assert Path(photo.file.path).read_bytes() == original
    generated = ItemPhoto.objects.filter(item__name__startswith="Estante de ferro").first()
    assert Path(generated.file.path).stat().st_size < 60_000  # continua a foto gerada


def test_photos_troca_as_fotos_sem_mexer_nos_leiloes(seeded, media, monkeypatch):
    from auctions.management.commands import seed_demo

    before = list(Auction.objects.order_by("id").values_list("id", "ends_at", "bid_count"))
    # simula um banco antigo: as fotos do notebook ainda eram as geradas
    photos = ItemPhoto.objects.filter(item__name__startswith="Notebook usado")
    for photo in photos:
        photo.file.save("foto.jpg", seed_demo._photo("Notebook", "eletronicos", 0), save=True)
    old_files = {p.file.path for p in ItemPhoto.objects.all()}

    call_command("seed_demo", photos=True, stdout=io.StringIO())

    assert before == list(Auction.objects.order_by("id").values_list("id", "ends_at", "bid_count"))
    assert ItemPhoto.objects.count() == 300
    original = (seed_demo.SEED_PHOTOS_DIR / "notebook.jpg").read_bytes()
    for photo in ItemPhoto.objects.filter(item__name__startswith="Notebook usado"):
        assert Path(photo.file.path).read_bytes() == original
    new_files = {p.file.path for p in ItemPhoto.objects.all()}
    assert not any(Path(path).exists() for path in old_files - new_files)
    assert len(list((media / "items").iterdir())) >= 300  # nada referenciado sumiu
    assert all(Path(path).is_file() for path in new_files)


def test_horarios_coerentes_com_o_status(seeded):
    now = seeded
    for auction in Auction.objects.all():
        assert auction.ends_at > auction.starts_at
        if auction.status == "running":
            assert auction.starts_at <= now < auction.ends_at
        elif auction.status == "scheduled":
            assert auction.starts_at > now
        elif auction.status in ("sold", "ended_no_bids"):
            assert auction.ends_at <= now


def test_ha_leiloes_curtos_para_a_demo(seeded):
    now = seeded
    soon = Auction.objects.filter(status="scheduled", starts_at__lte=now + timedelta(minutes=5))
    closing = Auction.objects.filter(status="running", ends_at__lte=now + timedelta(minutes=10))
    assert soon.count() >= 3 and closing.count() >= 3


def test_lances_respeitam_as_regras(seeded):
    for auction in Auction.objects.select_related("item", "leader"):
        bids = list(
            Bid.objects.filter(auction=auction).select_related("participant").order_by("created_at")
        )
        assert auction.bid_count == len(bids)
        if auction.status == "sold":
            assert bids
        if auction.status in ("ended_no_bids", "cancelled", "scheduled"):
            assert not bids
        highest, previous_user = None, None
        for bid in bids:
            assert type(bid.amount_cents) is int
            assert bid.amount_cents >= min_next_bid_cents(
                start_price_cents=auction.start_price_cents, highest_bid_cents=highest
            )
            assert bid.participant.user_id != auction.item.seller_id  # comitente não dá lance
            assert bid.participant.user_id != previous_user  # ninguém cobre o próprio lance
            assert auction.starts_at <= bid.created_at <= auction.ends_at
            highest, previous_user = bid.amount_cents, bid.participant.user_id
        if bids:
            assert auction.highest_bid_cents == highest
            assert auction.leader_id == bids[-1].participant_id
        else:
            assert auction.highest_bid_cents is None and auction.leader_id is None


def test_listagem_tem_varias_paginas(seeded, api):
    body = api.get("/api/auctions").json()
    assert body["total"] == Auction.objects.filter(status__in=["running", "scheduled"]).count()
    assert body["total"] > 4 * 12


def test_rodar_duas_vezes_nao_duplica(seeded):
    call_command("seed_demo", stdout=io.StringIO())
    assert Auction.objects.count() == 100 and User.objects.count() == 4
    assert ItemPhoto.objects.count() == 300


def test_reset_recria_e_apaga_as_fotos_antigas(seeded, media):
    old_files = {p.file.path for p in ItemPhoto.objects.all()}
    call_command("seed_demo", reset=True, stdout=io.StringIO())
    assert Auction.objects.count() == 100 and User.objects.count() == 4
    assert not any(Path(path).exists() for path in old_files)
    assert len(list((media / "items").iterdir())) == 300
