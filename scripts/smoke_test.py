#!/usr/bin/env python3
"""Fumaça de ponta a ponta pela API do contrato: cadastro, leilão, lances, fechamento.

    python3 scripts/smoke_test.py --base http://localhost:8000
    python3 scripts/smoke_test.py --base http://200.18.99.113:<porta> --no-wait-close

Leva ~3 a 4 min com os limites padrão (início em 30 s, duração de 60 s + prorrogação de 2 min).
Precisa do servidor E do worker no ar.
"""

import argparse
import time
import uuid

from _client import Api, check, expect, finish, parse_time, require_server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--no-wait-close", action="store_true", help="não espera o leilão fechar")
    args = parser.parse_args()

    seller, buyer, visitor = Api(args.base), Api(args.base), Api(args.base)
    config = require_server(visitor)
    limits = config["limits"]

    print("1. Contas (RF01-RF04)")
    seller.register_and_login("Vendedor Fumaça")
    buyer.register_and_login("Comprador Fumaça")
    status, _, _ = visitor.call("GET", "/api/auth/me")
    check(status == 401, "visitante sem sessão recebe 401 em /api/auth/me", status)
    status, _, _ = visitor.call("GET", "/api/auctions")
    check(status == 200, "listagem é pública", status)

    print("2. Criar leilão (RF05-RF07)")
    auction = seller.create_auction(
        start_price_cents=10_000,
        start_in=limits["min_start_delay_seconds"] + 3,
        duration=limits["min_duration_seconds"],
        name=f"Fumaça {uuid.uuid4().hex[:6]}",
    )
    auction_id = auction["id"]
    check(auction["status"] == "scheduled", "nasce agendado", auction["status"])
    check(len(auction["photos"]) >= limits["min_photos"], "fotos gravadas")
    check(auction["min_next_bid_cents"] == 10_000, "mínimo inicial = preço inicial (RF14)")

    print("3. Lance antes da abertura")
    status, body, _ = buyer.bid(auction_id, 10_000)
    check(status == 409 and body["code"] == "AUCTION_NOT_RUNNING", "recusado: não abriu", body)

    print("4. Abertura automática (RF17)")
    wait = limits["min_start_delay_seconds"] + 20
    seller.wait_status(auction_id, {"running"}, timeout=wait)
    check(True, "worker abriu o leilão no horário")

    print("5. Lances (RF10-RF12)")
    status, body, _ = seller.bid(auction_id, 10_000)
    check(status == 409 and body["code"] == "IS_SELLER", "comitente não dá lance", body)
    status, body, _ = buyer.bid(auction_id, 9_999)
    check(
        status == 409 and body["code"] == "BID_TOO_LOW" and body.get("min_bid_cents") == 10_000,
        "abaixo do mínimo: recusa informa o mínimo",
        body,
    )
    key = str(uuid.uuid4())
    status, first, _ = buyer.bid(auction_id, 10_000, key)
    expect(status == 201, "lance válido aceito", status, first)
    check("***" in first["bid"]["bidder_label"], "rótulo anônimo (RF09)", first["bid"])
    status, replay, headers = buyer.bid(auction_id, 10_000, key)
    check(
        status == 201 and replay["bid"]["id"] == first["bid"]["id"],
        "reenvio com a mesma chave devolve o MESMO lance (RF12)",
        replay,
    )
    check(headers.get("Idempotent-Replay") == "true", "header Idempotent-Replay: true")
    status, body, _ = buyer.bid(auction_id, 20_000, key)
    check(status == 422, "mesma chave com outro valor: 422", body)
    status, body, _ = buyer.bid(auction_id, 20_000)
    check(status == 409 and body["code"] == "IS_LEADER", "líder não cobre o próprio lance", body)
    _, detail, _ = visitor.call("GET", f"/api/auctions/{auction_id}")
    check(
        detail["bid_count"] == 1 and detail["current_price_cents"] == 10_000, "um lance só", detail
    )
    check("leader_label" not in detail, "detalhe público não mostra o líder (RF04)")

    if args.no_wait_close:
        return finish("smoke (sem esperar o fechamento)")

    print("6. Fechamento automático (RF15, RF17)")
    ends_at = parse_time(first["auction"]["ends_at"])
    server_now = parse_time(first["auction"]["server_time"])
    remaining = (ends_at - server_now).total_seconds()
    print(f"  … término vigente em {remaining:.0f}s (já com prorrogação); esperando")
    time.sleep(max(0, remaining - 1))
    final = seller.wait_status(auction_id, {"sold", "ended_no_bids", "cancelled"}, timeout=20)
    check(final["status"] == "sold", "com lances termina VENDIDO", final["status"])
    result = final.get("result") or {}
    check(result.get("final_price_cents") == 10_000, "resultado com o valor final", result)
    status, body, _ = buyer.bid(auction_id, 50_000)
    check(
        status == 409 and body["code"] == "AUCTION_NOT_RUNNING", "nada de lance após fechar", body
    )

    finish("smoke")


if __name__ == "__main__":
    main()
