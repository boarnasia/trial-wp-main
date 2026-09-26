import secrets

import typer

from ...docker import compose
from ...sites import parse_env

VERSION = 3
DESCRIPTION = "ダッシュボードを Django 版に切り替え、wp-main の .env に DJANGO_SECRET_KEY を加える"
REQUIRES_SUDO = False
DESTRUCTIVE = False
LOSES = ""

KEY = "DJANGO_SECRET_KEY"


def add_secret_key(ctx) -> None:
    env = ctx.main_dir / ".env"
    if not env.exists():
        typer.echo(f"  {env} がないため、{KEY} は追加しません")
        return
    text = env.read_text()
    if parse_env(text).get(KEY):
        typer.echo(f"  {KEY}: 変更なし")
        return
    if ctx.runner.dry_run:
        typer.echo(f"[dry-run] {env} に {KEY} を追加")
        return
    separator = "" if not text or text.endswith("\n") else "\n"
    env.write_text(f"{text}{separator}{KEY}={secrets.token_urlsafe(50)}\n")
    typer.echo(f"  {KEY}: 追加")


def up(ctx) -> None:
    add_secret_key(ctx)
    running = compose(ctx.runner, "ps", "--status", "running", "-q", "caddy", cwd=ctx.main_dir, check=False, mutate=False)
    # 停止中の環境を勝手に起動しない。次の docker compose up で反映される
    if running.returncode != 0 or not running.stdout.strip():
        typer.echo("  プロキシが停止しているため、コンテナは起動しません。次の docker compose up -d --build で反映されます")
        return
    compose(ctx.runner, "up", "-d", "--build", "--wait", cwd=ctx.main_dir)
