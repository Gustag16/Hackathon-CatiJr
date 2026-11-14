"""Erros de negócio levantados pelos serviços; as views traduzem para o formato do contrato."""


class NotSeller(Exception):
    """403 FORBIDDEN: só o comitente cancela o próprio leilão."""


class CannotCancel(Exception):
    """409 CANNOT_CANCEL com `reason`: HAS_BIDS ou ALREADY_FINISHED."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class InvalidTransition(Exception):
    """Transição fora das 5 permitidas pela RN01. É bug, não erro de usuário."""
