"""Lance mínimo (RF14): função pura do estado do leilão, sempre em centavos inteiros."""

# (limite superior EXCLUSIVO do preço atual, incremento), tudo em centavos.
# Tabela de referência do PDF: "Até R$ 99,99 -> R$ 1,00" vira (10_000, 100).
INCREMENT_TABLE: tuple[tuple[int, int], ...] = (
    (10_000, 100),  # até R$ 99,99           -> R$ 1,00
    (50_000, 500),  # R$ 100,00 a 499,99     -> R$ 5,00
    (100_000, 1_000),  # R$ 500,00 a 999,99  -> R$ 10,00
    (500_000, 5_000),  # R$ 1.000 a 4.999,99 -> R$ 50,00
    (2_500_000, 10_000),  # R$ 5.000 a 24.999,99 -> R$ 100,00
)
TOP_INCREMENT_CENTS = 50_000  # a partir de R$ 25.000,00 -> R$ 500,00


def _require_cents(name: str, value: object) -> int:
    # `type(...) is int` de propósito: recusa float, Decimal, str e bool (RF19).
    if type(value) is not int:
        raise TypeError(f"{name} deve ser int em centavos, veio {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} não pode ser negativo")
    return value


def increment_for(price_cents: int) -> int:
    """Incremento que vale quando o preço atual é `price_cents`."""
    _require_cents("price_cents", price_cents)
    for upper_bound, increment in INCREMENT_TABLE:
        if price_cents < upper_bound:
            return increment
    return TOP_INCREMENT_CENTS


def min_next_bid_cents(*, start_price_cents: int, highest_bid_cents: int | None) -> int:
    """Menor valor aceito para o próximo lance.

    Sem lances: o próprio preço inicial (o 1º lance pode ser igual a ele).
    Com lances: maior lance + incremento da faixa em que o maior lance está.
    """
    _require_cents("start_price_cents", start_price_cents)
    if highest_bid_cents is None:
        return start_price_cents
    _require_cents("highest_bid_cents", highest_bid_cents)
    return highest_bid_cents + increment_for(highest_bid_cents)
