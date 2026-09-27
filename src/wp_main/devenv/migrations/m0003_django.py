from ._env import add_secret, rebuild_if_running

VERSION = 3
DESCRIPTION = "ダッシュボードを Django 版に切り替え、wp-main の .env に DJANGO_SECRET_KEY を加える"
REQUIRES_SUDO = False
DESTRUCTIVE = False
LOSES = ""


def up(ctx) -> None:
    add_secret(ctx, "DJANGO_SECRET_KEY")
    rebuild_if_running(ctx)
