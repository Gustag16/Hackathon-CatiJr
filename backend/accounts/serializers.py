"""Formato JSON dos usuários (contrato, seção 2)."""


def user_json(user) -> dict:
    """`User`: só para o próprio usuário, porque traz o e-mail."""
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "email": user.email,
        "created_at": user.created_at,
    }


def public_user_json(user) -> dict:
    """`PublicUser`: o que qualquer visitante pode ver (sem e-mail)."""
    return {"id": str(user.id), "display_name": user.display_name, "created_at": user.created_at}
