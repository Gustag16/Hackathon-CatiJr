"""Configuração do Django. Tudo que muda entre dev e VM vem do .env (ver .env.example)."""

from pathlib import Path

from .env import database_from_url, env_bool, env_int, env_list, env_str, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "dev-inseguro-troque-no-env")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Sem django.contrib.admin de propósito: RF03 diz que não existe administrador.
INSTALLED_APPS = [
    "daphne",  # precisa vir antes de staticfiles: faz o runserver falar ASGI/WebSocket
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "accounts",
    "auctions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = []

DATABASES = {
    "default": database_from_url(
        env_str("DATABASE_URL", "postgresql://leilao:leilao@localhost:5432/leilao")
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# Tempo: UTC no banco, sempre o relógio do servidor (RF16, RF19).
USE_TZ = True
TIME_ZONE = "UTC"
USE_I18N = False

# Auth: sessão em cookie HttpOnly + CSRF, expiração deslizante (RF02, D2).
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE_SECONDS", 3600)
SESSION_SAVE_EVERY_REQUEST = True  # renova a cada uso
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # o front lê o cookie para mandar o X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "config.api_errors.exception_handler",
    "UNAUTHENTICATED_USER": None,
}

STATIC_URL = "/static/"

# Fotos: disco local da VM (D5). Só o caminho vai para o banco.
MEDIA_ROOT = Path(env_str("MEDIA_ROOT", "./media")).resolve()
MEDIA_URL = env_str("MEDIA_URL", "/media/")

# Limites de criação de leilão (RF05/RF06): mesmos nomes do `limits` em GET /api/config.
AUCTION_LIMITS = {
    "min_photos": env_int("MIN_PHOTOS", 3),
    "max_photos": env_int("MAX_PHOTOS", 8),
    "max_photo_bytes": env_int("MAX_PHOTO_BYTES", 5 * 1024 * 1024),
    "accepted_photo_types": env_list("ACCEPTED_PHOTO_TYPES", "image/jpeg,image/png,image/webp"),
    "max_name_length": env_int("MAX_NAME_LENGTH", 100),
    "max_description_length": env_int("MAX_DESCRIPTION_LENGTH", 2000),
    "min_duration_seconds": env_int("MIN_DURATION_SECONDS", 60),
    "max_duration_seconds": env_int("MAX_DURATION_SECONDS", 7 * 24 * 3600),
    "min_start_delay_seconds": env_int("MIN_START_DELAY_SECONDS", 30),
    "max_start_advance_seconds": env_int("MAX_START_ADVANCE_SECONDS", 30 * 24 * 3600),
}

# Categorias fixas (contrato, seção 3): id = slug.
AUCTION_CATEGORIES = [
    ("automoveis", "Automóveis"),
    ("moveis", "Móveis"),
    ("eletronicos", "Eletrônicos"),
    ("arte", "Arte"),
    ("hobbies-e-musica", "Hobbies e música"),
    ("colecionaveis", "Colecionáveis"),
    ("outros", "Outros"),
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"line": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "line"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
