from pathlib import Path
from typing import Annotated

import typer
from django.core.management import call_command

from django_typer.management import Typer

from .... import processes, session
from ....config import DASHBOARD_DOMAIN, resolve_root
from ....runner import DevEnvError, Runner
from ....sites import dashboard_port

app = Typer(help="開発セッションを始める: 共有インフラ・指定したサイト・ダッシュボードを起動し、終了時にサイトを止める")
# DB がまだない環境でも動かすため、DB に接続するシステムチェックは行わない
Command.requires_system_checks = []  # noqa: F821  Typer() がこのモジュールに Command を作る


def fail(message: str) -> typer.Exit:
    typer.secho(f"エラー: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(1)


@app.command()
def serve(
    site: Annotated[
        str | None, typer.Option("--site", help="起動するサイト（カンマ区切りのサイト ID、または all）。省略するとサイトは起動しない")
    ] = None,
    root: Annotated[
        Path | None, typer.Option("--root", help="wp-wp1 / wp-wp2 を置くディレクトリ（既定: wp-main の親）")
    ] = None,
) -> None:
    """開発セッションを始める（Ctrl-C で終了し、動いているサイトを止める）。"""
    try:
        sites = session.resolve_sites(site)
        port = dashboard_port()
    except DevEnvError as error:
        raise fail(str(error)) from error
    if processes.port_in_use(port):
        raise fail(f"127.0.0.1:{port} は使用中です。止めるか、wp-main の .env の DASHBOARD_PORT で別のポートを指定してください")
    try:
        call_command("migrate", verbosity=0, interactive=False)
    except Exception as error:
        raise fail(f"DB を準備できません: {error}") from error

    runner, root_dir = Runner(), resolve_root(root)
    try:
        session.begin(runner, sites, root_dir)
    except DevEnvError as error:
        raise fail(f"共有インフラを起動できません: {error}") from error

    code = 1
    try:
        typer.secho(f"https://{DASHBOARD_DOMAIN}/ (127.0.0.1:{port}) で起動します。Ctrl-C で終了します", fg=typer.colors.CYAN)
        code = processes.supervise(processes.host_processes(port, root_dir))
    finally:
        try:
            session.end(runner, root_dir)
        except KeyboardInterrupt:
            typer.secho("サイトの停止を中断しました。次の serve の終了時に止まります", fg=typer.colors.YELLOW, err=True)
            code = 1
    raise typer.Exit(code)
