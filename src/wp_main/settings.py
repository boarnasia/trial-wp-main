import os

from django.core.management.utils import get_random_secret_key

from .config import DASHBOARD_DOMAIN, DB_FILE, MAIN_DIR
from .sites import SECRET_PLACEHOLDER, read_env


def secret_key() -> str:
    # gunicorn の worker ごとに値が変わると、署名付き Cookie（操作結果のメッセージ）が別の worker で読めない
    value = os.environ.get("DJANGO_SECRET_KEY") or read_env(MAIN_DIR).get("DJANGO_SECRET_KEY", "")
    # devenv install は .env を作る前にも動くため、ない場合はその場限りの値で動かす
    return value if value and value != SECRET_PLACEHOLDER else get_random_secret_key()


SECRET_KEY = secret_key()
DEBUG = os.environ.get("DJANGO_DEBUG", "").lower() in ("1", "true", "yes")
# check-health は 127.0.0.1 のポートに直接 /healthz を取りに来る
ALLOWED_HOSTS = [DASHBOARD_DOMAIN, "127.0.0.1", "localhost"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_typer",
    "wp_main.cli",
    "wp_main.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ダッシュボードはホストの Docker を操作するため、別のサイトからの POST を拒否する
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# セッション用の DB を持たないため、操作結果のメッセージは Cookie で渡す
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
# Caddy の背後で動くので、Origin ヘッダーは常にダッシュボードの HTTPS のオリジンになる
CSRF_TRUSTED_ORIGINS = [f"https://{DASHBOARD_DOMAIN}"]
CSRF_COOKIE_SECURE = True

ROOT_URLCONF = "wp_main.urls"
WSGI_APPLICATION = "wp_main.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# ダッシュボードと CLI はどちらもホストで動き、同じファイルを直接開く
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH") or DB_FILE,
        # gunicorn の複数 worker と CLI が同時に書き込んだときに、即座に失敗せず待たせる
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
