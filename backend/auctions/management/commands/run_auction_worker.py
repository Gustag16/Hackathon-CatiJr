"""Worker que abre e fecha leilões lendo o BANCO a cada 1 s (RF17, RF18).

ESQUELETO: o Danilo implementa. Nada de timer em memória: se o processo morrer e voltar,
a próxima passada encontra no banco tudo o que ficou para trás.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Abre e fecha leilões no horário (loop de 1 s lendo o banco)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="uma passada só (testes/demo)")

    def handle(self, *args, **options):
        # TODO(Danilo): loop { open_due_auctions(); close_due_auctions(); sleep(1) },
        # com try/except por passada (um erro não derruba o worker), log de quantos
        # abriu/fechou e encerramento limpo em SIGTERM (docker stop).
        raise NotImplementedError("TODO(Danilo): loop do worker (RF17, RF18)")
