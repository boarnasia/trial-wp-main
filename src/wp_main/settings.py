import os

from django.core.management.utils import get_random_secret_key

from .config import DASHBOARD_DOMAIN, LOCAL_DIR

# devenv install は .env を作る前に動くため必須にしない。署名を使う機能を入れるまでは一時的な値で足りる
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or get_random_secret_key()
DEBUG = os.environ.get("DJANGO_DEBUG", "").lower() in ("1", "true", "yes")
# コンテナの healthcheck は 127.0.0.1:8000 に直接来る
ALLOWED_HOSTS = [DASHBOARD_DOMAIN, "127.0.0.1", "localhost"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django_typer",
    "wp_main.cli",
    "wp_main.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "wp_main.urls"
WSGI_APPLICATION = "wp_main.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {},
    }
]

# 書き込むのは Web 側だけにする（macOS の bind mount では SQLite のロックが信頼できない）
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH") or LOCAL_DIR / "db.sqlite3",
        # gunicorn の複数 worker が同時に書き込んだときに、即座に失敗せず待たせる
        "OPTIONS": {"timeout": 5, "init_command": "PRAGMA journal_mode=WAL;"},
    }
}

STATIC_URL = "/static/"
# 静的ファイルは 2 つだけなので collectstatic を省き、app の static/ から直接配る
WHITENOISE_USE_FINDERS = True

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
