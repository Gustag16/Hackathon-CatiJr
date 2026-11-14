import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


def normalize_email(email: str) -> str:
    """RF01: um e-mail identifica uma única conta (sem maiúsculas e sem espaços nas pontas)."""
    return email.strip().lower()


class UserManager(BaseUserManager):
    def create_user(self, email: str, display_name: str, password: str):
        user = self.model(email=normalize_email(email), display_name=display_name.strip())
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email: str):
        return self.get(email=normalize_email(email))


class User(AbstractBaseUser):
    """Todo usuário é comprador e pode anunciar (RF03). Não há papel de administrador."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]
    is_active = True

    def __str__(self) -> str:
        return self.email
