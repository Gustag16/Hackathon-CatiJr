"""Cliente HTTP mínimo (só biblioteca padrão) que fala o contrato: sessão por cookie + CSRF.

Usado por smoke_test.py e stress_bids.py. Não precisa de venv: `python3 scripts/...`.
"""

import json
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from http.cookiejar import CookieJar


def tiny_png(color: tuple[int, int, int] = (200, 60, 60), size: int = 16) -> bytes:
    """PNG válido de `size` x `size` pixels, gerado na hora (sem arquivo no repo)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    row = b"\x00" + bytes(color) * size
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * size))
        + chunk(b"IEND", b"")
    )


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Api:
    """Uma instância = um navegador (um pote de cookies)."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self) -> str:
        for cookie in self.jar:
            if cookie.name == "csrftoken":
                return cookie.value
        self.call("GET", "/api/auth/csrf")
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def call(self, method: str, path: str, body=None, headers=None, raw: bytes | None = None):
        """Devolve (status, corpo JSON ou None, cabeçalhos). Nunca levanta por 4xx/5xx."""
        headers = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if method != "GET":
            headers["X-CSRFToken"] = self._csrf()
            headers.setdefault("Referer", self.base + "/")
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers=headers
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                status, payload, response_headers = (
                    response.status,
                    response.read(),
                    response.headers,
                )
        except urllib.error.HTTPError as error:
            status, payload, response_headers = error.code, error.read(), error.headers
        try:
            parsed = json.loads(payload) if payload else None
        except ValueError:
            parsed = {"_raw": payload[:300].decode(errors="replace")}
        return status, parsed, response_headers

    def multipart(self, path: str, fields: dict, files: list[tuple[str, str, str, bytes]]):
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            parts.append(f"{head}{value}\r\n".encode())
        for name, filename, content_type, content in files:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode()
                + content
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self.call("POST", path, headers=headers, raw=b"".join(parts))

    # ----- atalhos do contrato -----

    def register_and_login(self, display_name: str) -> str:
        email = f"{display_name.lower().replace(' ', '.')}.{uuid.uuid4().hex[:8]}@teste.dev"
        password = "senha-de-teste-123"
        status, body, _ = self.call(
            "POST",
            "/api/auth/register",
            {"display_name": display_name, "email": email, "password": password},
        )
        expect(status == 201, f"cadastro de {display_name}", status, body)
        status, body, _ = self.call(
            "POST", "/api/auth/login", {"email": email, "password": password}
        )
        expect(status == 200, f"login de {display_name}", status, body)
        return email

    def create_auction(self, *, start_price_cents: int, start_in: int, duration: int, name: str):
        _, config, _ = self.call("GET", "/api/config")
        starts_at = parse_time(config["server_time"]) + timedelta(seconds=start_in)
        photos = [
            ("photos", f"foto{i}.png", "image/png", tiny_png((40 + 60 * i, 90, 160)))
            for i in range(config["limits"]["min_photos"])
        ]
        fields = {
            "name": name,
            "description": "Criado por script de teste.",
            "category": "outros",
            "start_price_cents": start_price_cents,
            "starts_at": iso(starts_at),
            "duration_seconds": duration,
        }
        status, body, _ = self.multipart("/api/auctions", fields, photos)
        expect(status == 201, "criar leilão", status, body)
        return body

    def bid(self, auction_id: str, amount_cents: int, key: str | None = None):
        return self.call(
            "POST",
            f"/api/auctions/{auction_id}/bids",
            {"amount_cents": amount_cents},
            headers={"Idempotency-Key": key or str(uuid.uuid4())},
        )

    def wait_status(self, auction_id: str, wanted: set[str], timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            _, detail, _ = self.call("GET", f"/api/auctions/{auction_id}")
            if detail and detail.get("status") in wanted:
                return detail
            if time.monotonic() > deadline:
                fail(f"leilão não chegou a {wanted} em {timeout:.0f}s (status: {detail})")
            time.sleep(1)


FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f"  \033[32m✔\033[0m {message}")


def check(condition: bool, message: str, detail: object = "") -> bool:
    """Confere e continua (acumula as falhas para o resumo final)."""
    if condition:
        ok(message)
    else:
        FAILURES.append(message)
        print(f"  \033[31m✘\033[0m {message} {detail}")
    return condition


def expect(condition: bool, message: str, status: object = "", body: object = "") -> None:
    """Confere e PARA se falhar (não dá para seguir sem este passo)."""
    if not check(condition, message, f"-> HTTP {status} {body}"):
        fail("passo obrigatório falhou")


def fail(message: str) -> None:
    print(f"\n\033[31mFALHOU:\033[0m {message}")
    sys.exit(1)


def finish(name: str) -> None:
    if FAILURES:
        print(f"\n\033[31m{name}: {len(FAILURES)} verificação(ões) falharam\033[0m")
        for failure in FAILURES:
            print(f"  - {failure}")
        sys.exit(1)
    print(f"\n\033[32m{name}: tudo certo\033[0m")


def require_server(api: Api) -> dict:
    try:
        status, body, _ = api.call("GET", "/api/config")
    except OSError as error:
        fail(f"não consegui falar com {api.base} ({error}). O backend está no ar? (make backend)")
    if status != 200:
        fail(
            f"GET /api/config devolveu {status}: a API do contrato ainda não existe neste servidor"
        )
    return body
