"""RF14 e RF15 ligados ao lance de verdade (as contas em si estão em tests/unit)."""

from datetime import timedelta

import pytest

from .conftest import bid

pytestmark = pytest.mark.django_db

MIN = timedelta(minutes=1)


def test_minimo_sobe_pela_tabela_a_cada_lance(make_auction, ana, bruno):
    auction = make_auction(start_price_cents=9_900)  # R$ 99,00: faixa de R$ 1,00
    assert bid(ana, auction, 9_900).body["auction"]["min_next_bid_cents"] == 10_000
    # R$ 100,00 entra na faixa de R$ 5,00
    assert bid(bruno, auction, 10_000).body["auction"]["min_next_bid_cents"] == 10_500


def test_lance_acima_do_minimo_e_aceito_e_vira_a_base(running, ana, bruno):
    bid(ana, running, 10_000)
    outcome = bid(bruno, running, 80_000)  # R$ 800,00: faixa de R$ 10,00
    assert outcome.status_code == 201
    assert outcome.body["auction"]["min_next_bid_cents"] == 81_000


def test_lance_com_folga_nao_prorroga(running, ana, clock):
    ends_at = running.ends_at
    clock.set(ends_at - 2 * MIN)  # restam exatamente 2 min
    bid(ana, running, 10_000)
    running.refresh_from_db()
    assert running.ends_at == ends_at


def test_lance_a_menos_de_2_min_do_fim_prorroga(
    running, ana, clock, sent, django_capture_on_commit_callbacks
):
    original = running.ends_at
    clock.set(original - timedelta(seconds=10))
    with django_capture_on_commit_callbacks(execute=True):
        bid(ana, running, 10_000)

    running.refresh_from_db()
    assert running.ends_at == clock.now + 2 * MIN
    assert running.original_ends_at == original  # o original nunca muda
    assert sent[0]["message"]["extended"] is True


def test_prorrogacao_acumulada_para_em_30_min(running, ana, bruno, clock):
    original = running.ends_at
    amount = 10_000
    for i in range(40):  # dois compradores se alternando sempre a 1 s do fim
        running.refresh_from_db()
        clock.set(running.ends_at - timedelta(seconds=1))
        assert bid(ana if i % 2 == 0 else bruno, running, amount).status_code == 201
        amount += 10_000
    running.refresh_from_db()
    assert running.ends_at == original + 30 * MIN
    assert running.original_ends_at == original


def test_no_teto_o_lance_vale_mas_o_fim_nao_anda(running, ana, clock):
    type(running).objects.filter(id=running.id).update(ends_at=running.ends_at + 30 * MIN)
    running.refresh_from_db()
    clock.set(running.ends_at - timedelta(seconds=1))
    assert bid(ana, running, 10_000).status_code == 201
    ends_before = running.ends_at
    running.refresh_from_db()
    assert running.ends_at == ends_before
