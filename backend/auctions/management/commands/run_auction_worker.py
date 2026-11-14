"""Worker que abre e fecha leilões lendo o BANCO a cada 1 s (RF17, RF18).

    python manage.py run_auction_worker          # loop até receber SIGTERM/Ctrl+C
    python manage.py run_auction_worker --once   # uma passada só (testes e diagnóstico)

Não guarda nada em memória: cada passada pergunta ao banco "quem já devia ter aberto?" e
"quem já devia ter fechado?". Se o processo (ou a VM) cair e voltar, a primeira passada
encontra tudo o que ficou para trás. Pode rodar mais de uma cópia ao mesmo tempo: o
`skip_locked` faz cada leilão ser processado por uma só.
"""

import logging
import signal
import threading
import time

from django.core.management.base import BaseCommand
from django.db import connections

from auctions.services.transitions import close_due_auctions, open_due_auctions

logger = logging.getLogger("auctions.worker")
HEARTBEAT_EVERY = 60  # passadas (~1 min): prova nos logs que o worker está vivo


class Command(BaseCommand):
    help = "Abre e fecha leilões no horário (loop de 1 s lendo o banco)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="uma passada só")
        parser.add_argument("--interval", type=float, default=1.0, help="segundos entre passadas")
        parser.add_argument("--passes", type=int, default=0, help="parar após N passadas (testes)")

    def handle(self, *args, once=False, interval=1.0, passes=0, **options):
        if once:
            self._pass(raise_errors=True)  # no modo --once, erro aparece para quem chamou
            return

        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):  # `docker stop` manda SIGTERM
            signal.signal(sig, lambda *_: stop.set())
        logger.info("worker iniciado (intervalo de %.1f s)", interval)

        count = 0
        while not stop.is_set():
            started = time.monotonic()
            self._pass(raise_errors=False)
            count += 1
            if count % HEARTBEAT_EVERY == 0:
                logger.info("worker vivo (%d passadas)", count)
            if passes and count >= passes:
                break
            # Espera o resto do segundo, mas acorda na hora se chegar um SIGTERM: a passada
            # em andamento sempre termina (a transação nunca é cortada no meio).
            stop.wait(max(0.0, interval - (time.monotonic() - started)))
        logger.info("worker encerrado")

    def _pass(self, *, raise_errors: bool) -> None:
        try:
            opened = open_due_auctions()
            closed = close_due_auctions()
            if opened or closed:
                logger.info("abertos: %d, fechados: %d", opened, closed)
        except Exception:
            if raise_errors:
                raise
            # Ex.: banco reiniciando. Não derruba o worker: fecha as conexões (a próxima
            # passada abre uma nova) e tenta de novo em 1 s. Nada se perde, está tudo no banco.
            logger.exception("passada do worker falhou; tentando de novo")
            connections.close_all()
