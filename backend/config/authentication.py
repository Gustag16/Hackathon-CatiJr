"""Autenticação por sessão que cobra CSRF em TODO método que altera estado.

O SessionAuthentication do DRF só confere o CSRF quando já existe um usuário logado. Assim,
login e cadastro ficariam sem CSRF, e um site de terceiros poderia logar o navegador da
vítima numa conta do atacante ("login CSRF"). O contrato diz que o front manda `X-CSRFToken`
em todo POST/PATCH/DELETE, então aqui a conferência vale com ou sem sessão.
GET/HEAD/OPTIONS nunca são conferidos (o próprio CSRFCheck do Django ignora métodos seguros).
"""

from rest_framework.authentication import SessionAuthentication


class CsrfSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        self.enforce_csrf(request)
        user = getattr(request._request, "user", None)
        if not user or not user.is_active:
            return None
        return (user, None)
