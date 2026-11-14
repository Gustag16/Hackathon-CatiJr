"""Prorrogação (RF15): lance perto do fim empurra o término, com teto acumulado."""

from datetime import datetime, timedelta

EXTENSION_WINDOW = timedelta(minutes=2)
MAX_TOTAL_EXTENSION = timedelta(minutes=30)


def extended_ends_at(*, now: datetime, ends_at: datetime, original_ends_at: datetime) -> datetime:
    """Novo término depois de um lance ACEITO no instante `now`.

    Pré-condição (de quem chama, dentro da trava): `now < ends_at`.
    Se restam menos de 2 min: `min(now + 2 min, original_ends_at + 30 min)`.
    Senão devolve `ends_at` sem mudar. O resultado nunca é menor que `ends_at`.
    """
    for name, value in (("now", now), ("ends_at", ends_at), ("original_ends_at", original_ends_at)):
        if value.tzinfo is None:
            raise ValueError(f"{name} precisa ter fuso (UTC); veio datetime ingênuo")
    if now >= ends_at:
        raise ValueError("lance depois do término não prorroga: deveria ter sido recusado")
    if ends_at - now >= EXTENSION_WINDOW:
        return ends_at
    return min(now + EXTENSION_WINDOW, original_ends_at + MAX_TOTAL_EXTENSION)


def was_extended(*, old_ends_at: datetime, new_ends_at: datetime) -> bool:
    """Valor do campo `extended` do evento `bid_accepted`."""
    return new_ends_at > old_ends_at
