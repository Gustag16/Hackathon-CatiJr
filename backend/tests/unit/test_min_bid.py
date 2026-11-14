"""RF14: lance mínimo é função pura do estado, em centavos (tabela de referência do PDF)."""

import pytest

from auctions.rules.min_bid import increment_for, min_next_bid_cents


def test_sem_lances_o_minimo_e_o_preco_inicial():
    assert min_next_bid_cents(start_price_cents=5_000, highest_bid_cents=None) == 5_000


@pytest.mark.parametrize(
    ("price_cents", "increment_cents"),
    [
        (1, 100),
        (9_999, 100),  # R$ 99,99
        (10_000, 500),  # R$ 100,00
        (49_999, 500),
        (50_000, 1_000),  # R$ 500,00
        (99_999, 1_000),
        (100_000, 5_000),  # R$ 1.000,00
        (499_999, 5_000),
        (500_000, 10_000),  # R$ 5.000,00
        (2_499_999, 10_000),
        (2_500_000, 50_000),  # R$ 25.000,00
        (900_000_000, 50_000),
    ],
)
def test_incremento_nas_bordas_de_cada_faixa(price_cents, increment_cents):
    assert increment_for(price_cents) == increment_cents
    assert (
        min_next_bid_cents(start_price_cents=1, highest_bid_cents=price_cents)
        == price_cents + increment_cents
    )


def test_minimo_cresce_a_cada_lance_aceito():
    highest = None
    previous_min = 0
    for _ in range(200):
        minimum = min_next_bid_cents(start_price_cents=100, highest_bid_cents=highest)
        assert minimum > previous_min
        previous_min, highest = minimum, minimum


def test_mesmo_estado_mesmo_resultado():
    args = {"start_price_cents": 1_000, "highest_bid_cents": 123_456}
    assert min_next_bid_cents(**args) == min_next_bid_cents(**args)


@pytest.mark.parametrize("bad", [10.0, "1000", True, None])
def test_recusa_o_que_nao_e_inteiro_em_centavos(bad):
    """RF19: float nunca entra na conta de dinheiro."""
    with pytest.raises(TypeError):
        min_next_bid_cents(start_price_cents=bad, highest_bid_cents=None)
    with pytest.raises(TypeError):
        increment_for(bad)


def test_recusa_valor_negativo():
    with pytest.raises(ValueError):
        increment_for(-1)
