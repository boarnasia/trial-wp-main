import secrets

import typer

from ...docker import compose
from ...sites import parse_env


def add_secret(ctx, key: str) -> None:
    """wp-main の .env に key がなければランダム値を追記する。既存の値は変えない。"""
    env = ctx.main_dir / ".env"
    if not env.exists():
        typer.echo(f"  {env} がないため、{key} は追加しません")
        return
    text = env.read_text()
    if parse_env(text).get(key):
        typer.echo(f"  {key}: 変更なし")
        return
    if ctx.runner.dry_run:
        typer.echo(f"[dry-run] {env} に {key} を追加")
        return
    separator = "" if not text or text.endswith("\n") else "\n"
    env.write_text(f"{text}{separator}{key}={secrets.token_urlsafe(50)}\n")
    typer.echo(f"  {key}: 追加")


def rebuild_if_running(ctx) -> None:
    running = compose(ctx.runner, "ps", "--status", "running", "-q", "caddy", cwd=ctx.main_dir, check=False, mutate=False)
    # 停止中の環境を勝手に起動しない。次の docker compose up で反映される
    if running.returncode != 0 or not running.stdout.strip():
        typer.echo("  プロキシが停止しているため、コンテナは起動しません。次の docker compose up -d --build で反映されます")
        return
    compose(ctx.runner, "up", "-d", "--build", "--wait", cwd=ctx.main_dir)
