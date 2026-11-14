"""RF11: lances simultâneos nunca deixam o sistema inconsistente, e a sala só vê o estado
depois do commit. Estes testes usam threads e transações de verdade."""

import pytest
from django.db import transaction

from auctions.models import Auction, Bid
from auctions.rules.min_bid import min_next_bid_cents
from auctions.services.errors import CannotCancel
from auctions.services.transitions import cancel_auction

from .conftest import bid, run_parallel


@pytest.mark.django_db(transaction=True)
def test_20_lances_simultaneos_no_mesmo_valor_so_um_e_aceito(running, make_user):
    users = [make_user(f"User{i}") for i in range(20)]
    outcomes = run_parallel([lambda u=u: bid(u, running, 10_000) for u in users])

    assert sorted(o.status_code for o in outcomes) == [201] + [409] * 19
    assert {o.body["code"] for o in outcomes if o.status_code == 409} == {"BID_TOO_LOW"}
    assert Bid.objects.count() == 1
    running.refresh_from_db()
    assert running.bid_count == 1 and running.highest_bid_cents == 10_000


@pytest.mark.django_db(transaction=True)
def test_30_lances_simultaneos_de_valores_diferentes_respeitam_a_regra_do_valor(running, make_user):
    """Valores espaçados de R$ 5,00 (o incremento da faixa): o maior SEMPRE é aceito, e
    nunca ficam gravados dois lances que juntos violem o lance mínimo."""
    users = [make_user(f"User{i}") for i in range(30)]
    amounts = [10_000 + 500 * i for i in range(30)]
    outcomes = run_parallel(
        [lambda u=u, a=a: bid(u, running, a) for u, a in zip(users, amounts, strict=True)]
    )

    accepted = sorted(o.body["bid"]["amount_cents"] for o in outcomes if o.status_code == 201)
    stored = list(Bid.objects.order_by("amount_cents").values_list("amount_cents", flat=True))
    assert stored == accepted and len(set(stored)) == len(stored)
    assert all(o.status_code in (201, 409) for o in outcomes)

    highest = None
    for amount in stored:  # cada lance gravado respeitava o mínimo do anterior
        assert amount >= min_next_bid_cents(start_price_cents=10_000, highest_bid_cents=highest)
        highest = amount

    running.refresh_from_db()
    assert running.highest_bid_cents == max(amounts) == stored[-1]
    assert running.bid_count == len(stored)
    assert running.leader.user_id == users[-1].id
    numbers = sorted(running.participants.values_list("number", flat=True))
    assert numbers == list(range(1, len(numbers) + 1))  # numeração sem buraco nem repetição


@pytest.mark.django_db(transaction=True)
def test_lance_e_cancelamento_simultaneos_so_um_vence(make_auction, seller, ana):
    """RF08/RF18: cancelar usa a MESMA trava do lance. Nunca sobra lance aceito em leilão
    cancelado."""
    for _ in range(10):
        auction = make_auction()

        def try_cancel(auction=auction):
            try:
                cancel_auction(user=seller, auction_id=auction.id)
                return "cancelled"
            except CannotCancel as exc:
                return exc.reason

        outcome, cancel = run_parallel([lambda a=auction: bid(ana, a, 10_000), try_cancel])
        auction.refresh_from_db()
        if outcome.status_code == 201:
            assert cancel == "HAS_BIDS" and auction.status == "running" and auction.bid_count == 1
        else:
            assert outcome.body["code"] == "AUCTION_NOT_RUNNING"
            assert cancel == "cancelled" and auction.status == "cancelled"
            assert auction.bids.count() == 0


@pytest.mark.django_db
def test_broadcast_so_depois_do_commit(running, ana, sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        outcome = bid(ana, running, 10_000)
        assert outcome.status_code == 201
        assert sent == []  # ainda dentro da transação: a sala não pode ter visto nada

    assert len(sent) == 1
    assert sent[0]["group"] == f"auction_{running.id}"
    message = sent[0]["message"]
    assert message["type"] == "bid_accepted" and message["extended"] is False
    assert message["bid"]["amount_cents"] == 10_000
    assert message["auction"]["min_next_bid_cents"] == 10_500


@pytest.mark.django_db
def test_lance_recusado_nao_gera_broadcast(
    running, seller, sent, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        bid(seller, running, 10_000)
    assert sent == []


@pytest.mark.django_db(transaction=True)
def test_rollback_nao_gera_broadcast_nem_lance(running, ana, sent):
    """Se a transação de fora falhar depois do lance, a sala nunca fica sabendo."""

    class Boom(Exception):
        pass

    with pytest.raises(Boom), transaction.atomic():
        bid(ana, running, 10_000)
        raise Boom

    assert sent == [] and Bid.objects.count() == 0
    assert Auction.objects.get(id=running.id).bid_count == 0
