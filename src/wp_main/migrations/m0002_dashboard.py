import typer

from ..devenv import hosts_domains
from ..docker import compose
from .. import hosts

VERSION = 2
DESCRIPTION = "ダッシュボードを導入し、プロキシのポートを 127.0.0.1 に限定する"
REQUIRES_SUDO = True
DESTRUCTIVE = False
LOSES = ""


def up(ctx) -> None:
    new_hosts = hosts.with_block(hosts.HOSTS_FILE.read_text(), hosts_domains())
    typer.echo("  /etc/hosts: " + ("更新" if hosts.write_hosts(ctx.runner, new_hosts) else "変更なし"))

    running = compose(ctx.runner, "ps", "--status", "running", "-q", "caddy", cwd=ctx.main_dir, check=False, mutate=False)
    # 停止中の環境を勝手に起動しない。次の docker compose up で反映される
    if running.returncode != 0 or not running.stdout.strip():
        typer.echo("  プロキシが停止しているため、コンテナは起動しません。次の docker compose up -d で反映されます")
        return
    # ポートの公開範囲が変わった Caddy を作り直し、ダッシュボードをビルドして起動する
    compose(ctx.runner, "up", "-d", "--build", "--wait", cwd=ctx.main_dir)
