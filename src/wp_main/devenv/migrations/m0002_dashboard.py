import typer

from ... import hosts
from .. import hosts_domains
from ._env import rebuild_if_running

VERSION = 2
DESCRIPTION = "ダッシュボードを導入し、プロキシのポートを 127.0.0.1 に限定する"
REQUIRES_SUDO = True
DESTRUCTIVE = False
LOSES = ""


def up(ctx) -> None:
    new_hosts = hosts.with_block(hosts.HOSTS_FILE.read_text(), hosts_domains())
    typer.echo("  /etc/hosts: " + ("更新" if hosts.write_hosts(ctx.runner, new_hosts) else "変更なし"))

    # ポートの公開範囲が変わった Caddy を作り直す
    rebuild_if_running(ctx)
