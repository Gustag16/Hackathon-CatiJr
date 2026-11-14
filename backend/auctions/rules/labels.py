"""Rótulo anônimo do participante (RF09, D4): "Danilo" + nº 3 -> "Dan*** #3"."""


def mask_name(display_name: str) -> str:
    """Primeiros max(1, min(3, tamanho // 2)) caracteres + "***" (contrato, seção 2)."""
    name = display_name.strip()
    visible = max(1, min(3, len(name) // 2))
    return name[:visible] + "***"


def participant_label(display_name: str, participant_number: int) -> str:
    if type(participant_number) is not int or participant_number < 1:
        raise ValueError("participant_number começa em 1")
    return f"{mask_name(display_name)} #{participant_number}"
