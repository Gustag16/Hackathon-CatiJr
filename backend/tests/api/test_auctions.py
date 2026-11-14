"""Item 3 da etapa 1: criar, listar e detalhar leilões (RF04, RF05-RF07, RF19, RF20)."""

import uuid
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from auctions.models import Auction, Item, ItemPhoto

from .conftest import image_bytes

pytestmark = pytest.mark.django_db

SUMMARY_KEYS = {
    "id", "item_id", "name", "category", "cover_photo_url", "status", "starts_at", "ends_at",
    "current_price_cents", "bid_count", "seller",
}  # fmt: skip
PUBLIC_KEYS = {
    "id", "item_id", "status", "starts_at", "ends_at", "original_ends_at",
    "current_price_cents", "min_next_bid_cents", "bid_count", "server_time",
}  # fmt: skip
DETAIL_KEYS = SUMMARY_KEYS | PUBLIC_KEYS | {"description", "photos", "start_price_cents", "result"}


def iso(value) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def photos(n=3, fmt="PNG", name="foto.png"):
    return [SimpleUploadedFile(name, image_bytes(fmt), content_type="image/png") for _ in range(n)]


@pytest.fixture
def form(clock):
    return {
        "name": "Violão Giannini",
        "description": "Pouco uso, cordas novas.",
        "category": "hobbies-e-musica",
        "start_price_cents": "12500",
        "starts_at": iso(clock.now + timedelta(seconds=60)),
        "duration_seconds": "180",
    }


def post(api, form, files=None):
    return api.post("/api/auctions", {**form, "photos": photos() if files is None else files})


# ---------- criação ----------


def test_cria_item_e_primeiro_leilao(logged, form, media, clock):
    api, user = logged
    response = post(api, form)

    assert response.status_code == 201, response.json()
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert body["status"] == "scheduled"
    assert body["starts_at"] == "2030-01-01T12:01:00Z"
    assert body["ends_at"] == body["original_ends_at"] == "2030-01-01T12:04:00Z"
    assert body["start_price_cents"] == body["current_price_cents"] == 12_500
    assert body["min_next_bid_cents"] == 12_500  # 1º lance pode ser igual ao preço inicial
    assert body["bid_count"] == 0 and body["result"] is None
    assert body["seller"] == {
        "id": str(user.id), "display_name": user.display_name,
        "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
    }  # fmt: skip
    assert body["server_time"] == "2030-01-01T12:00:00Z"
    assert Item.objects.get().auctions.count() == 1


def test_fotos_gravadas_com_nome_uuid_e_url_relativa(logged, form, media):
    api, _ = logged
    body = post(api, form, [SimpleUploadedFile("../../etc/passwd.png", image_bytes())] * 1
                + photos(2)).json()  # fmt: skip
    assert len(body["photos"]) == 3
    for photo in body["photos"]:
        name = photo["url"].removeprefix("/media/items/")
        assert photo["url"].startswith("/media/items/") and name.endswith(".png")
        uuid.UUID(name.removesuffix(".png"))  # nome é um UUID, não o nome enviado
        assert (media / "items" / name).is_file()
    assert body["cover_photo_url"] == body["photos"][0]["url"]


def test_extensao_vem_do_conteudo_e_nao_do_nome(logged, form, media):
    api, _ = logged
    files = [SimpleUploadedFile("foto.png", image_bytes("JPEG")) for _ in range(3)]
    body = post(api, form, files).json()
    assert all(p["url"].endswith(".jpg") for p in body["photos"])


def test_aceita_webp(logged, form, media):
    api, _ = logged
    files = [SimpleUploadedFile("x.webp", image_bytes("WEBP")) for _ in range(3)]
    assert post(api, form, files).status_code == 201


def test_criar_exige_login(api, form, media):
    response = post(api, form)
    assert response.status_code == 401 and response.json()["code"] == "NOT_AUTHENTICATED"
    assert Auction.objects.count() == 0


@pytest.mark.parametrize("count", [0, 2, 9])
def test_quantidade_de_fotos(logged, form, media, count):
    api, _ = logged
    response = post(api, form, photos(count))
    assert response.status_code == 400
    assert response.json()["fields"]["photos"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"MZ isto nao e imagem" * 10, "não é uma imagem válida"),
        (image_bytes("GIF"), "tipo não aceito (aceitos: jpeg, png, webp)"),
        (image_bytes("BMP"), "tipo não aceito (aceitos: jpeg, png, webp)"),
        (image_bytes("PNG")[:40], "não é uma imagem válida"),  # truncado
    ],
    ids=["executavel-renomeado", "gif", "bmp", "png-truncado"],
)
def test_foto_validada_pelo_conteudo(logged, form, media, content, reason):
    api, _ = logged
    fake = SimpleUploadedFile("foto.jpg", content, content_type="image/jpeg")
    response = post(api, form, photos(2) + [fake])
    assert response.status_code == 400
    assert response.json()["fields"]["photos"] == [f"Foto 3: {reason}."]
    assert ItemPhoto.objects.count() == 0 and not any(media.rglob("*.*"))


def test_foto_acima_do_tamanho(logged, form, media, settings):
    settings.AUCTION_LIMITS = {**settings.AUCTION_LIMITS, "max_photo_bytes": 50}
    api, _ = logged
    response = post(api, form)
    assert response.status_code == 400 and "limite" in response.json()["fields"]["photos"][0]


def test_tipos_aceitos_vem_da_config(logged, form, media, settings):
    settings.AUCTION_LIMITS = {**settings.AUCTION_LIMITS, "accepted_photo_types": ["image/jpeg"]}
    api, _ = logged
    assert post(api, form).status_code == 400  # PNG deixou de ser aceito


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "x" * 101),
        ("description", "   "),
        ("description", "x" * 2001),
        ("category", "carros"),
        ("start_price_cents", "125.00"),  # nunca float (RF19)
        ("start_price_cents", "1e4"),
        ("start_price_cents", "0"),
        ("start_price_cents", "-500"),
        ("start_price_cents", "abc"),
        ("start_price_cents", "9999999999999"),
        ("duration_seconds", "59"),
        ("duration_seconds", "604801"),
        ("duration_seconds", "90.5"),
        ("starts_at", "amanhã"),
        ("starts_at", "2030-01-01T12:10:00"),  # sem fuso
    ],
)
def test_campo_invalido(logged, form, media, field, value):
    api, _ = logged
    response = post(api, {**form, field: value})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR" and list(body["fields"]) == [field]
    assert Auction.objects.count() == 0


def test_varios_erros_de_uma_vez(logged, media):
    api, _ = logged
    response = api.post("/api/auctions", {})
    expected = "name description category start_price_cents duration_seconds starts_at photos"
    assert set(response.json()["fields"]) == set(expected.split())


def test_inicio_minimo_e_pelo_relogio_do_servidor(logged, form, media, clock):
    api, _ = logged
    too_soon = {**form, "starts_at": iso(clock.now + timedelta(seconds=29))}
    assert post(api, too_soon).status_code == 400
    just_ok = {**form, "starts_at": iso(clock.now + timedelta(seconds=30))}
    assert post(api, just_ok).status_code == 201


def test_inicio_maximo(logged, form, media, clock, settings):
    api, _ = logged
    limit = settings.AUCTION_LIMITS["max_start_advance_seconds"]
    late = {**form, "starts_at": iso(clock.now + timedelta(seconds=limit + 1))}
    assert post(api, late).json()["fields"]["starts_at"]


def test_demo_curta_abre_em_1_minuto_e_dura_3(logged, form, media):
    """RF06: o exemplo do PDF tem que passar com os limites padrão."""
    api, _ = logged
    assert post(api, {**form, "duration_seconds": "180"}).status_code == 201


def test_data_com_outro_fuso_vira_utc(logged, form, media):
    api, _ = logged
    body = post(api, {**form, "starts_at": "2030-01-01T09:05:00-03:00"}).json()
    assert body["starts_at"] == "2030-01-01T12:05:00Z"


def test_dinheiro_sai_como_inteiro(logged, form, media):
    api, _ = logged
    body = post(api, form).json()
    for key in ("start_price_cents", "current_price_cents", "min_next_bid_cents"):
        assert type(body[key]) is int


# ---------- listagem (RF20) ----------


def test_listagem_publica_com_formato_do_contrato(api, make_auction, clock):
    make_auction()
    body = api.get("/api/auctions").json()
    assert set(body) == {"results", "page", "page_size", "total", "server_time"}
    assert (body["page"], body["page_size"], body["total"]) == (1, 12, 1)
    assert set(body["results"][0]) == SUMMARY_KEYS
    assert set(body["results"][0]["seller"]) == {"id", "display_name", "created_at"}  # sem e-mail
    assert body["results"][0]["cover_photo_url"] is None  # leilão de teste sem foto


def test_listagem_so_mostra_agendados_e_em_andamento(api, make_auction):
    for status in ("scheduled", "running", "sold", "ended_no_bids", "cancelled"):
        make_auction(status=status, starts_in=60 if status == "scheduled" else -300)
    statuses = {a["status"] for a in api.get("/api/auctions").json()["results"]}
    assert statuses == {"scheduled", "running"}


def test_ordem_running_por_termino_depois_scheduled_por_inicio(api, make_auction):
    s_late = make_auction(status="scheduled", starts_in=600)
    r_late = make_auction(status="running", starts_in=-60, duration=900)
    s_soon = make_auction(status="scheduled", starts_in=60)
    r_soon = make_auction(status="running", starts_in=-60, duration=120)
    ids = [a["id"] for a in api.get("/api/auctions").json()["results"]]
    assert ids == [str(a.id) for a in (r_soon, r_late, s_soon, s_late)]


def test_empate_desempata_por_id(api, make_auction):
    tied = [make_auction(status="scheduled", starts_in=60) for _ in range(5)]
    ids = [a["id"] for a in api.get("/api/auctions").json()["results"]]
    assert ids == sorted(str(a.id) for a in tied)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("running", {"running"}),
        ("scheduled", {"scheduled"}),
        ("scheduled,running", {"running", "scheduled"}),
    ],
)
def test_filtro_de_status(api, make_auction, query, expected):
    make_auction(status="running")
    make_auction(status="scheduled", starts_in=60)
    body = api.get(f"/api/auctions?status={query}").json()
    assert {a["status"] for a in body["results"]} == expected and body["total"] == len(expected)


@pytest.mark.parametrize(
    "query",
    [
        "status=sold",
        "status=running,sold",
        "status=,",
        "page=0",
        "page=x",
        "page_size=49",
        "page_size=0",
    ],
)
def test_parametros_invalidos(api, query):
    response = api.get(f"/api/auctions?{query}")
    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_paginacao(api, make_auction):
    created = [make_auction(status="scheduled", starts_in=60 + i) for i in range(30)]
    first = api.get("/api/auctions?page=1").json()
    third = api.get("/api/auctions?page=3").json()
    assert first["total"] == third["total"] == 30
    assert len(first["results"]) == 12 and len(third["results"]) == 6
    assert third["results"][-1]["id"] == str(created[-1].id)
    assert api.get("/api/auctions?page=4").json()["results"] == []
    assert len(api.get("/api/auctions?page_size=48").json()["results"]) == 30


def test_listagem_nao_mostra_lider(api, make_auction, make_user):
    make_auction(highest=15_000, winner=make_user("Bruno"))
    text = str(api.get("/api/auctions").json())
    assert "leader" not in text and "Bru" not in text


def test_listagem_sem_consultas_por_leilao(api, make_auction, django_assert_max_num_queries):
    for _ in range(12):
        make_auction()
    with django_assert_max_num_queries(4):  # count + leilões + fotos (sem N+1)
        api.get("/api/auctions")


# ---------- detalhe (RF04) ----------


def test_detalhe_publico_sem_lider_e_sem_lances(api, make_auction, make_user):
    auction = make_auction(highest=15_000, winner=make_user("Bruno"))
    response = api.get(f"/api/auctions/{auction.id}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert body["current_price_cents"] == 15_000 and body["min_next_bid_cents"] == 15_500
    assert "Bru" not in str(body) and body["result"] is None


@pytest.mark.parametrize("bad", [uuid.uuid4(), "nao-e-uuid"])
def test_detalhe_inexistente_e_not_found(api, bad):
    response = api.get(f"/api/auctions/{bad}")
    assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"


def test_detalhe_de_vendido_mostra_resultado_anonimo(api, make_auction, make_user):
    auction = make_auction(status="sold", highest=15_000, winner=make_user("Bruno Lima"))
    result = api.get(f"/api/auctions/{auction.id}").json()["result"]
    assert result == {"status": "sold", "winner_label": "Bru*** #1", "final_price_cents": 15_000}


def test_detalhe_de_encerrado_sem_lances(api, make_auction):
    auction = make_auction(status="ended_no_bids")
    result = api.get(f"/api/auctions/{auction.id}").json()["result"]
    assert result == {"status": "ended_no_bids", "winner_label": None, "final_price_cents": None}


def test_finalizados_continuam_acessiveis_pelo_link(api, make_auction):
    auction = make_auction(status="cancelled")
    body = api.get(f"/api/auctions/{auction.id}").json()
    assert body["status"] == "cancelled" and body["result"] is None


def test_criado_aparece_na_listagem_e_no_detalhe(logged, form, media):
    api, _ = logged
    created = post(api, form).json()
    listed = api.get("/api/auctions").json()["results"]
    assert [a["id"] for a in listed] == [created["id"]]
    assert api.get(f"/api/auctions/{created['id']}").json()["photos"] == created["photos"]
