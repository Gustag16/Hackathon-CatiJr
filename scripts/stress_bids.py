#!/usr/bin/env python3
"""50 compradores dão lance AO MESMO TEMPO no mesmo leilão; depois confere as invariantes.

    python3 scripts/stress_bids.py --base http://localhost:8000 --bidders 50

O que tem que valer no fim (RF11, RF12, RF14):
  - só respostas 201 ou 409 (nenhum 5xx);
  - nenhum par de lances aceitos com o mesmo valor;
  - na ordem dos valores, cada lance aceito respeita o mínimo do anterior;
  - o maior valor enviado foi aceito e é o preço atual;
  - bid_count = quantidade de 201;
  - reenviar TODAS as chaves devolve os mesmos resultados e não cria lance.
A regra do mínimo é importada de backend/auctions/rules (módulo puro, sem Django).
"""

import argparse
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _client import Api, check, finish, require_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from auctions.rules.min_bid import min_next_bid_cents  # noqa: E402

START_CENTS = 10_000
STEP_CENTS = 500  # incremento da faixa R$ 100-499,99


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--bidders", type=int, default=50)
    args = parser.parse_args()
    count = args.bidders
    if START_CENTS + (count // 2) * STEP_CENTS >= 50_000:
        sys.exit("use até 150 compradores (os valores precisam ficar na mesma faixa)")

    seller = Api(args.base)
    limits = require_server(seller)["limits"]

    print(f"1. Preparando 1 comitente e {count} compradores")
    seller.register_and_login("Vendedor Carga")
    bidders = [Api(args.base) for _ in range(count)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        list(
            pool.map(
                lambda pair: pair[1].register_and_login(f"Carga {pair[0]}"), enumerate(bidders)
            )
        )
    auction = seller.create_auction(
        start_price_cents=START_CENTS,
        start_in=limits["min_start_delay_seconds"] + 3,
        duration=max(limits["min_duration_seconds"], 120),
        name=f"Carga {uuid.uuid4().hex[:6]}",
    )
    auction_id = auction["id"]
    seller.wait_status(auction_id, {"running"}, timeout=limits["min_start_delay_seconds"] + 20)

    # Dois compradores por valor: disputa pelo MESMO valor e entre valores vizinhos.
    amounts = [START_CENTS + (i // 2) * STEP_CENTS for i in range(count)]
    keys = [str(uuid.uuid4()) for _ in range(count)]

    def fire(barrier):
        def one(index):
            barrier.wait(timeout=30)
            status, body, headers = bidders[index].bid(auction_id, amounts[index], keys[index])
            return status, body, headers.get("Idempotent-Replay")

        with ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(one, range(count)))

    print(f"2. {count} lances simultâneos")
    results = fire(threading.Barrier(count))
    statuses = [status for status, _, _ in results]
    accepted = sorted(body["bid"]["amount_cents"] for status, body, _ in results if status == 201)
    print(f"  aceitos: {len(accepted)} · recusados: {statuses.count(409)} · outros: "
          f"{[s for s in statuses if s not in (201, 409)]}")  # fmt: skip

    check(all(status in (201, 409) for status in statuses), "só 201 ou 409 (nenhum 5xx)", statuses)
    check(len(accepted) >= 1, "pelo menos um lance aceito")
    check(len(set(accepted)) == len(accepted), "nenhum valor aceito duas vezes", accepted)
    highest, respects = None, True
    for amount in accepted:
        minimum = min_next_bid_cents(start_price_cents=START_CENTS, highest_bid_cents=highest)
        respects = respects and amount >= minimum
        highest = amount
    check(respects, "cada lance aceito respeita o mínimo do anterior (RF11)", accepted)
    check(max(amounts) in accepted, "o maior valor enviado foi aceito", max(amounts))
    refusals = [body for status, body, _ in results if status == 409]
    check(
        all(b.get("code") and "min_next_bid_cents" in b.get("auction", {}) for b in refusals),
        "toda recusa traz o motivo e o mínimo atual (RF10)",
    )
    print(f"  motivos: {sorted({b.get('code') for b in refusals})}")

    _, detail, _ = seller.call("GET", f"/api/auctions/{auction_id}")
    check(detail["bid_count"] == len(accepted), "bid_count = nº de 201", detail["bid_count"])
    check(detail["current_price_cents"] == max(accepted, default=0), "preço atual = maior lance")
    expected_min = min_next_bid_cents(
        start_price_cents=START_CENTS, highest_bid_cents=max(accepted, default=None)
    )
    check(detail["min_next_bid_cents"] == expected_min, "mínimo seguinte bate com a tabela (RF14)")

    print("3. Reenvio de todas as chaves ao mesmo tempo (RF12)")
    replays = fire(threading.Barrier(count))
    same = all(
        again[0] == first[0]
        and (again[1].get("bid") or {}).get("id") == (first[1].get("bid") or {}).get("id")
        and again[1].get("code") == first[1].get("code")
        for first, again in zip(results, replays, strict=True)
    )
    check(same, "cada reenvio devolveu o resultado ORIGINAL")
    check(all(flag == "true" for _, _, flag in replays), "todos com Idempotent-Replay: true")
    _, after, _ = seller.call("GET", f"/api/auctions/{auction_id}")
    check(after["bid_count"] == detail["bid_count"], "nenhum lance novo criado pelo reenvio")

    finish("stress")


if __name__ == "__main__":
    main()
