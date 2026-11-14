"""Único lugar que lê o relógio do servidor (RF16).

Os testes trocam esta função (monkeypatch) para "viajar no tempo". No lance, chame
`clock.now()` DEPOIS de obter a trava da linha: um lance que esperou na fila da trava
tem que ser julgado pela hora em que é processado, não pela hora em que chegou.
"""

from datetime import datetime

from django.utils import timezone


def now() -> datetime:
    return timezone.now()
