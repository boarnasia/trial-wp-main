import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from django.core.management import call_command

from django_typer.management import Typer

from .... import logs, power, processes, session
from ....config import DASHBOARD_DOMAIN, MAIN_DIR, resolve_root
from ....runner import DevEnvError, Runner
from ....sites import dashboard_port

app = Typer(help="開発セッションを始める・終える・ログを見る（up / down / logs）")
# DB がまだない環境でも動かすため、DB に接続するシステムチェックは行わない
Command.requires_system_checks = []  # noqa: F821  Typer() がこのモジュールに Command を作る

SiteOption = Annotated[
    str | None, typer.Option("--site", help="起動するサイト（カンマ区切りのサイト ID、または all）。省略するとサイトは起動しない")
]
RootOption = Annotated[
    Path | None, typer.Option("--root", help="wp-wp1 / wp-wp2 を置くディレクトリ（既定: wp-main の親）")
]
DETACH_POLL_SECONDS = 0.5
LOG_TAIL_ON_FAILURE = 20


def fail(message: str) -> typer.Exit:
    typer.secho(f"エラー: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(1)


def prepare_db() -> None:
    call_command("migrate", verbosity=0, interactive=False)


# サブコマンドのない以前の書き方（serve --site=...）を受け取って案内するため、--site をここでも受け付ける
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, legacy_site: Annotated[str | None, typer.Option("--site", hidden=True)] = None) -> None:
    if ctx.invoked_subcommand is None:
        example = f"uv run manage.py serve up --site={legacy_site}" if legacy_site else "uv run manage.py serve up"
        raise fail(f"サブコマンドを指定してください（up / down / logs）。開発セッションを始めるには: {example}")


def detach(sites: str, root: Path) -> int:
    """監督プロセスを端末から切り離して起動し、開発セッションが始まるか失敗するまで待つ。"""
    command = [sys.executable, str(MAIN_DIR / "manage.py"), "serve", "supervise", "--root", str(root)]
    if sites:
        command += ["--site", sites]
    serve_log = session.LOG_DIR / session.SERVE_LOG
    serve_log.parent.mkdir(parents=True, exist_ok=True)
    with open(serve_log, "a") as log:
        child = subprocess.Popen(
            command, cwd=MAIN_DIR, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    while child.poll() is None:
        info = session.status()
        if info and info.pid == child.pid and info.state == session.READY:
            typer.secho(f"https://{DASHBOARD_DOMAIN}/ で開発セッションを始めました（PID {child.pid}）", fg=typer.colors.GREEN)
            for site_id in info.failed:
                typer.secho(f"{site_id} は起動できませんでした。uv run manage.py serve logs serve で原因を確認してください",
                            fg=typer.colors.YELLOW, err=True)
            typer.echo("ログ: uv run manage.py serve logs -f / 終了: uv run manage.py serve down")
            return 0
        time.sleep(DETACH_POLL_SECONDS)
    tail = logs.last_lines(serve_log, LOG_TAIL_ON_FAILURE)
    typer.secho(f"開発セッションを始められませんでした（exit {child.returncode}）。serve.log の末尾:", fg=typer.colors.RED, err=True)
    for line in tail:
        typer.echo(f"  {line.rstrip()}", err=True)
    typer.echo("詳しくは uv run manage.py serve logs を確認してください", err=True)
    return 1


@app.command()
def up(
    site: SiteOption = None,
    detach_: Annotated[bool, typer.Option("--detach", "-d", help="端末から切り離して動かす")] = False,
    root: RootOption = None,
) -> None:
    """開発セッションを始める: 共有インフラ・指定したサイト・ダッシュボードを起動する（Ctrl-C または serve down で終了）。"""
    try:
        sites = session.resolve_sites(site)
        port = dashboard_port()
    except DevEnvError as error:
        raise fail(str(error)) from error
    root_dir = resolve_root(root)

    current = session.status()
    if current:
        typer.echo(f"動いている開発セッション（PID {current.pid}）を終えてから始めます（共有インフラはそのまま使います）")
        try:
            session.request_end(signal.SIGUSR1)
        except DevEnvError as error:
            raise fail(f"{error}。uv run manage.py serve down で止めてください") from error
    if processes.port_in_use(port):
        raise fail(f"127.0.0.1:{port} は使用中です。止めるか、wp-main の .env の DASHBOARD_PORT で別のポートを指定してください")
    session.rotate_logs()

    if detach_:
        raise typer.Exit(detach(",".join(item.id for item in sites), root_dir))
    typer.secho("Ctrl-C で開発セッションを終了します（共有インフラも止まります）", fg=typer.colors.CYAN)
    try:
        code = session.supervise_session(Runner(), sites, root_dir, port, prepare=prepare_db, terminal=True)
    except session.Running as error:
        raise fail(f"{error}。先に uv run manage.py serve down で止めてください") from error
    raise typer.Exit(code)


@app.command(hidden=True)
def supervise(site: SiteOption = None, root: RootOption = None) -> None:
    """（内部用）serve up --detach が起動する、開発セッションの監督プロセス。"""
    try:
        code = session.supervise_session(
            Runner(), session.resolve_sites(site), resolve_root(root), dashboard_port(),
            prepare=prepare_db, terminal=False,
        )
    except (DevEnvError, session.Running) as error:
        raise fail(str(error)) from error
    raise typer.Exit(code)


@app.command()
def down(root: RootOption = None) -> None:
    """開発セッションを終える: ダッシュボード・動いているサイト・共有インフラを止める（ボリュームは残す）。"""
    runner, root_dir = Runner(), resolve_root(root)
    info = session.request_end(signal.SIGTERM, kill=True)
    if info:
        typer.echo(f"開発セッション（PID {info.pid}）を終了しました")
    # 監督プロセスが強制終了されていた場合に残ったものを片付ける
    leftovers = power.running_sites(runner)
    for item in leftovers:
        session.operate(runner, item, root_dir, "stop", typer.echo)
    infra = power.infra_exists(runner)
    stopped = session.stop_infra(runner, typer.echo) if infra else True
    stale = session.clear_stale()
    if not (info or leftovers or infra or stale):
        typer.echo("開発セッションはありません")
    raise typer.Exit(0 if stopped else 1)


@app.command("logs")
def show_logs(
    names: Annotated[list[str] | None, typer.Argument(help="表示するログの名前（serve・dashboard・caddy・mysql・サイト ID）")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help="新しい行を追い続ける（Ctrl-C で終了）")] = False,
    tail: Annotated[int | None, typer.Option("--tail", help="各ログの最後の N 行から表示する")] = None,
) -> None:
    """開発セッションのログ（ホストのプロセスとコンテナ）をまとめて表示する。"""
    try:
        selected = logs.select(names or [], Runner())
    except DevEnvError as error:
        raise fail(str(error)) from error
    if not selected:
        typer.echo("表示できるログがありません")
        return
    logs.show(selected, follow=follow, tail=tail)
