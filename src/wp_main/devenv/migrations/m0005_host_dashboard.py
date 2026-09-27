import sqlite3

import typer

from ...config import CADDY_IMAGE, LEGACY_DASHBOARD_CONTAINER, LEGACY_DASHBOARD_IMAGE, LEGACY_DASHBOARD_VOLUME
from ...runner import DevEnvError
from ._env import rebuild_if_running

VERSION = 5
DESCRIPTION = "ダッシュボードをホストの devenv serve に移し、旧ダッシュボードのコンテナ・イメージ・ボリュームを片付ける"
REQUIRES_SUDO = False
# 操作履歴は .local/db.sqlite3 に写してからボリュームを消すので、データは失われない
DESTRUCTIVE = False
LOSES = ""


def copy_history(ctx) -> None:
    local = ctx.main_dir / ".local"
    db = local / "db.sqlite3"
    if db.exists():
        typer.echo(f"  {db} があるため、ボリュームの履歴は写しません")
        return
    if ctx.runner.dry_run:
        typer.echo(f"[dry-run] {LEGACY_DASHBOARD_VOLUME} の DB を {db} に写す")
        return
    local.mkdir(exist_ok=True)
    # プロキシ用に必ずある caddy:2 を使い、新しいイメージの pull を起こさない
    ctx.runner.run([
        "docker", "run", "--rm", "-v", f"{LEGACY_DASHBOARD_VOLUME}:/data:ro", "-v", f"{local}:/out", CADDY_IMAGE,
        "sh", "-c", "if [ -f /data/db.sqlite3 ]; then cp /data/db.sqlite3 /out/; [ -f /data/db.sqlite3-wal ] && cp /data/db.sqlite3-wal /out/; true; fi",
    ])
    if not db.exists():
        typer.echo("  ボリュームに操作履歴はありません")
        return
    try:
        with sqlite3.connect(db) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.Error as error:
        result = str(error)
    if result != "ok":
        for path in (db, db.with_name("db.sqlite3-wal"), db.with_name("db.sqlite3-shm")):
            path.unlink(missing_ok=True)
        raise DevEnvError(f"写した操作履歴の DB を検証できません（{result}）。{LEGACY_DASHBOARD_VOLUME} は残しています")
    typer.echo(f"  操作履歴を {db} に写しました")


def up(ctx) -> None:
    runner = ctx.runner
    if runner.ok(["docker", "container", "inspect", LEGACY_DASHBOARD_CONTAINER]):
        runner.run(["docker", "rm", "-f", LEGACY_DASHBOARD_CONTAINER])
    if runner.ok(["docker", "volume", "inspect", LEGACY_DASHBOARD_VOLUME]):
        copy_history(ctx)
        runner.run(["docker", "volume", "rm", LEGACY_DASHBOARD_VOLUME])
    if runner.ok(["docker", "image", "inspect", LEGACY_DASHBOARD_IMAGE]):
        runner.run(["docker", "image", "rm", LEGACY_DASHBOARD_IMAGE])
    # Caddy の転送先と環境変数が変わるので、起動中なら作り直して新しい Caddyfile を読ませる
    rebuild_if_running(ctx)
    typer.secho("  ダッシュボードは別の端末で起動してください: uv run manage.py devenv serve", fg=typer.colors.CYAN)
