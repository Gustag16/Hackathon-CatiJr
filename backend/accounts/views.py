"""Contas (contrato, seção 3): csrf, register, login, logout, me.

Sessão Django em cookie HttpOnly. O CSRF é cobrado em todo POST pela classe
`config.authentication.CsrfSessionAuthentication` (inclusive login e cadastro).
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from config.api_errors import error_response

from .models import User, normalize_email
from .serializers import user_json

DISPLAY_NAME_MAX = User._meta.get_field("display_name").max_length


def _text(data, name: str) -> str:
    value = data.get(name, "")
    return value if isinstance(value, str) else ""


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Só faz o Django mandar o cookie `csrftoken`; o front lê e devolve em X-CSRFToken."""
    get_token(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """RF01. Cria a conta e NÃO loga (o front leva para o login)."""
    display_name = _text(request.data, "display_name").strip()
    email = normalize_email(_text(request.data, "email"))
    password = _text(request.data, "password")

    errors: dict[str, list[str]] = {}
    if not display_name:
        errors["display_name"] = ["Informe o nome de exibição."]
    elif len(display_name) > DISPLAY_NAME_MAX:
        errors["display_name"] = [f"No máximo {DISPLAY_NAME_MAX} caracteres."]
    try:
        validate_email(email)
    except DjangoValidationError:
        errors["email"] = ["E-mail inválido."]
    try:
        # Os validadores do Django (settings.AUTH_PASSWORD_VALIDATORS), comparando a senha
        # com o e-mail e o nome para recusar senhas parecidas com eles.
        validate_password(password, user=User(email=email, display_name=display_name))
    except DjangoValidationError as exc:
        errors["password"] = list(exc.messages)
    if errors:
        raise ValidationError(errors)

    if User.objects.filter(email=email).exists():
        return _email_taken()
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email, display_name=display_name, password=password
            )
    except IntegrityError:  # dois cadastros iguais ao mesmo tempo: o UNIQUE do banco decide
        return _email_taken()
    return Response(user_json(user), status=status.HTTP_201_CREATED)


def _email_taken() -> Response:
    return error_response("EMAIL_TAKEN", "Este e-mail já está cadastrado.", 409)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email = _text(request.data, "email")
    password = _text(request.data, "password")
    if not email or not password:
        errors = {}
        if not email:
            errors["email"] = ["Informe o e-mail."]
        if not password:
            errors["password"] = ["Informe a senha."]
        raise ValidationError(errors)

    # O backend padrão busca por get_by_natural_key, que normaliza o e-mail.
    user = authenticate(request._request, username=email, password=password)
    if user is None:
        # Mesma resposta para e-mail inexistente e senha errada: não revela quem tem conta.
        return error_response("INVALID_CREDENTIALS", "E-mail ou senha incorretos.", 401)
    login(request._request, user)  # gira o id da sessão e o token CSRF
    return Response({"user": user_json(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request._request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(user_json(request.user))
