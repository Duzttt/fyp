import os
from pathlib import Path

from app.config import settings as rag_settings

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-local-dev-key")
DEBUG = bool(rag_settings.DEBUG)
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_backend.middleware.CorsAllowAllMiddleware",
]

ROOT_URLCONF = "django_backend.urls"
WSGI_APPLICATION = "django_backend.wsgi.application"
ASGI_APPLICATION = "django_backend.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Frontend hits endpoints without trailing slash, e.g. /api/upload
APPEND_SLASH = False
