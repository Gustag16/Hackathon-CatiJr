"""Formato único de erro do contrato: { "code": ..., "message": ..., ...extras }."""

from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def error_response(code: str, message: str, http_status: int, **extras) -> Response:
    return Response({"code": code, "message": message, **extras}, status=http_status)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # erro inesperado: deixa virar 500
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        # O DRF devolveria 403 com SessionAuthentication; o contrato pede 401.
        return error_response(
            "NOT_AUTHENTICATED", "Faça login para continuar.", status.HTTP_401_UNAUTHORIZED
        )
    if isinstance(exc, exceptions.ValidationError):
        fields = response.data if isinstance(response.data, dict) else {"detail": response.data}
        return error_response(
            "VALIDATION_ERROR", "Dados inválidos.", status.HTTP_400_BAD_REQUEST, fields=fields
        )
    if response.status_code == status.HTTP_403_FORBIDDEN:
        return error_response("FORBIDDEN", "Você não tem permissão para isso.", 403)
    if response.status_code == status.HTTP_404_NOT_FOUND:
        return error_response("NOT_FOUND", "Recurso não encontrado.", 404)
    return error_response("ERROR", str(getattr(exc, "detail", exc)), response.status_code)
