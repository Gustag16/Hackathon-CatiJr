"""RF15: prorrogação de 2 min, com teto de 30 min sobre o término ORIGINAL."""

from datetime import UTC, datetime, timedelta

import pytest

from auctions.rules.extension import extended_ends_at, was_extended

T0 = datetime(2026, 11, 14, 18, 0, 0, tzinfo=UTC)  # término original
MIN = timedelta(minutes=1)
SEC = timedelta(seconds=1)


def test_lance_com_2_min_ou_mais_nao_prorroga():
    assert extended_ends_at(now=T0 - 2 * MIN, ends_at=T0, original_ends_at=T0) == T0
    assert extended_ends_at(now=T0 - 10 * MIN, ends_at=T0, original_ends_at=T0) == T0


def test_lance_com_menos_de_2_min_leva_o_termino_para_2_min_depois_do_lance():
    now = T0 - 2 * MIN + SEC  # restam 1min59s
    assert extended_ends_at(now=now, ends_at=T0, original_ends_at=T0) == now + 2 * MIN


def test_lance_no_ultimo_segundo():
    now = T0 - SEC
    assert extended_ends_at(now=now, ends_at=T0, original_ends_at=T0) == T0 + 2 * MIN - SEC


def test_prorrogacoes_sucessivas_param_em_30_min_sobre_o_original():
    ends_at = T0
    for _ in range(100):  # sempre um lance a 1 s do fim
        now = ends_at - SEC
        new_ends_at = extended_ends_at(now=now, ends_at=ends_at, original_ends_at=T0)
        assert new_ends_at >= ends_at  # nunca encurta
        assert new_ends_at <= T0 + 30 * MIN  # nunca passa do teto
        if new_ends_at == ends_at:
            break
        ends_at = new_ends_at
    assert ends_at == T0 + 30 * MIN


def test_no_teto_o_lance_e_aceito_mas_nao_prorroga():
    ends_at = T0 + 30 * MIN
    new_ends_at = extended_ends_at(now=ends_at - SEC, ends_at=ends_at, original_ends_at=T0)
    assert new_ends_at == ends_at
    assert was_extended(old_ends_at=ends_at, new_ends_at=new_ends_at) is False


def test_prorrogacao_parcial_perto_do_teto():
    ends_at = T0 + 29 * MIN
    now = ends_at - 30 * SEC  # now + 2 min passaria do teto
    assert extended_ends_at(now=now, ends_at=ends_at, original_ends_at=T0) == T0 + 30 * MIN


def test_was_extended():
    assert was_extended(old_ends_at=T0, new_ends_at=T0 + MIN) is True
    assert was_extended(old_ends_at=T0, new_ends_at=T0) is False


def test_recusa_datetime_sem_fuso():
    naive = datetime(2026, 11, 14, 17, 59, 30)  # noqa: DTZ001
    with pytest.raises(ValueError):
        extended_ends_at(now=naive, ends_at=T0, original_ends_at=T0)


def test_lance_no_instante_do_termino_e_erro_de_quem_chamou():
    with pytest.raises(ValueError):
        extended_ends_at(now=T0, ends_at=T0, original_ends_at=T0)
