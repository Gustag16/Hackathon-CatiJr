"""Configuração comum a todos os testes."""

import pytest


@pytest.fixture(autouse=True)
def _hash_de_senha_rapido(settings):
    """O hash de senha de produção é lento de propósito (~0,3 s); nos testes não precisa."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
