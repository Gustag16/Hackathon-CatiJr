"""Item 1 da etapa 1: contas (RF01, RF02, RF03)."""

import pytest

from accounts.models import User

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

GOOD = {"display_name": "Ana Paula", "email": "ana@teste.dev", "password": PASSWORD}


def test_csrf_devolve_204_e_seta_o_cookie(api):
    response = api.get("/api/auth/csrf")
    assert response.status_code == 204
    assert response.cookies["csrftoken"].value
    assert not response.cookies["csrftoken"]["httponly"]  # o front precisa ler


def test_cadastro_cria_e_nao_loga(api):
    response = api.post("/api/auth/register", GOOD, format="json")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "display_name", "email", "created_at"}
    assert body["email"] == "ana@teste.dev" and body["created_at"].endswith("Z")
    assert "password" not in str(body)
    assert api.get("/api/auth/me").status_code == 401  # não logou


def test_cadastro_normaliza_o_email(api):
    api.post("/api/auth/register", {**GOOD, "email": "  Ana@Teste.DEV "}, format="json")
    assert User.objects.get().email == "ana@teste.dev"


@pytest.mark.parametrize("variant", ["ana@teste.dev", "ANA@TESTE.DEV", "  ana@teste.dev  "])
def test_email_repetido_e_email_taken(api, variant):
    api.post("/api/auth/register", GOOD, format="json")
    response = api.post("/api/auth/register", {**GOOD, "email": variant}, format="json")
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN" and response.json()["message"]
    assert User.objects.count() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_name", ""),
        ("display_name", "   "),
        ("display_name", "x" * 61),
        ("email", "não-é-email"),
        ("password", "curta"),  # MinimumLengthValidator
        ("password", "12345678901"),  # NumericPasswordValidator
        ("password", "password123"),  # CommonPasswordValidator
        ("password", "ana@teste.dev"),  # UserAttributeSimilarityValidator
    ],
)
def test_cadastro_invalido_e_validation_error_com_fields(api, field, value):
    response = api.post("/api/auth/register", {**GOOD, field: value}, format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR" and body["message"]
    assert list(body["fields"]) == [field] and body["fields"][field]
    assert User.objects.count() == 0


def test_cadastro_sem_campos_lista_todos(api):
    body = api.post("/api/auth/register", {}, format="json").json()
    assert set(body["fields"]) == {"display_name", "email", "password"}


def test_json_quebrado_e_validation_error(api):
    response = api.post("/api/auth/register", "{nao json", content_type="application/json")
    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_login_ok_devolve_user_e_cria_sessao(api, make_user):
    user = make_user(email="bia@teste.dev")
    response = api.post(
        "/api/auth/login", {"email": " BIA@teste.dev", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)
    assert response.cookies["sessionid"]["httponly"]
    assert api.get("/api/auth/me").json()["email"] == "bia@teste.dev"


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "bia@teste.dev", "password": "senha-errada-1"},
        {"email": "ninguem@teste.dev", "password": PASSWORD},
    ],
)
def test_login_errado_e_invalid_credentials(api, make_user, credentials):
    make_user(email="bia@teste.dev")
    response = api.post("/api/auth/login", credentials, format="json")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_sem_campos_e_validation_error(api):
    response = api.post("/api/auth/login", {}, format="json")
    assert response.status_code == 400 and set(response.json()["fields"]) == {"email", "password"}


def test_me_sem_sessao_e_401(api):
    response = api.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"code": "NOT_AUTHENTICATED", "message": "Faça login para continuar."}


def test_logout_encerra_a_sessao(logged):
    api, _ = logged
    assert api.post("/api/auth/logout").status_code == 204
    assert api.get("/api/auth/me").status_code == 401


def test_logout_sem_sessao_e_401(api):
    assert api.post("/api/auth/logout").status_code == 401


def test_sessao_expira_e_renova_com_o_uso(settings):
    """RF02/D2: 1 h deslizante, vinda do .env."""
    assert settings.SESSION_COOKIE_AGE == 3600 and settings.SESSION_SAVE_EVERY_REQUEST


# ---------- CSRF de verdade (como no navegador) ----------


def test_post_sem_token_csrf_e_recusado_mesmo_no_login(csrf_api, make_user):
    make_user(email="bia@teste.dev")
    response = csrf_api.post(
        "/api/auth/login", {"email": "bia@teste.dev", "password": PASSWORD}, format="json"
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN" and "CSRF" in response.json()["message"]


def test_fluxo_completo_com_csrf(csrf_api):
    token = csrf_api.get("/api/auth/csrf").cookies["csrftoken"].value
    response = csrf_api.post("/api/auth/register", GOOD, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201

    credentials = {"email": GOOD["email"], "password": PASSWORD}
    response = csrf_api.post("/api/auth/login", credentials, format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200

    # O login gira o token: o front precisa reler o cookie (o antigo deixa de valer).
    new_token = response.cookies["csrftoken"].value
    assert new_token != token
    assert csrf_api.post("/api/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 403
    assert csrf_api.post("/api/auth/logout", HTTP_X_CSRFTOKEN=new_token).status_code == 204
