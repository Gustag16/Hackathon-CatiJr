"""RF09/D4: o líder aparece sem o nome completo: "Dan*** #3"."""

import pytest

from auctions.rules.labels import mask_name, participant_label


@pytest.mark.parametrize(
    ("name", "masked"),
    [
        ("Danilo", "Dan***"),  # exemplo do contrato
        ("Gus", "G***"),  # exemplo do contrato
        ("Ana Paula Souza", "Ana***"),
        ("Bia", "B***"),
        ("Jo", "J***"),
        ("X", "X***"),
        ("  Amadeu  ", "Ama***"),
        ("Érica", "Ér***"),
    ],
)
def test_mask_name(name, masked):
    assert mask_name(name) == masked


@pytest.mark.parametrize("name", ["Danilo", "Gus", "Jo", "Maria Clara", "Zé"])
def test_nunca_expoe_o_nome_completo(name):
    label = participant_label(name, 1)
    assert name not in label
    assert len(label.split("***")[0]) < len(name)


def test_participant_label():
    assert participant_label("Danilo", 3) == "Dan*** #3"


@pytest.mark.parametrize("bad", [0, -1, "3", 1.0])
def test_numero_do_participante_comeca_em_1(bad):
    with pytest.raises(ValueError):
        participant_label("Danilo", bad)
