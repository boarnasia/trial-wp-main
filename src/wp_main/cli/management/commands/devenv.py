from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from django_typer.management import Typer

from .... import __version__, devenv, health, operations, versioning
from ....config import resolve_root
from ....runner import DevEnvError, Runner

app = Typer(help="wp-main: マルチリポジトリ WordPress 開発環境の管理 CLI")
# CLI はホストで動き、DB を開かない。JSONField のシステムチェックは DB に接続するため行わない
Command.requires_system_checks = []  # noqa: F821  Typer() がこのモジュールに Command を作る

# 移行そのものや状態の確認、情報表示では警告を出さない
NO_VERSION_WARNING = {"migrate", "check-health", "version"}


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand in NO_VERSION_WARNING:
        return
    try:
        message = versioning.outdated_message(resolve_root(None))
    except Exception as error:  # 警告の判定に失敗しても、本来のコマンドは止めない
        typer.secho(f"警告: 環境バージョンを確認できません: {error}", fg=typer.colors.YELLOW, err=True)
        return
    if message:
        typer.secho(f"警告: {message}", fg=typer.colors.YELLOW, err=True)


RootOption = Annotated[
    Path | None, typer.Option("--root", help="wp-wp1 / wp-wp2 を置くディレクトリ（既定: wp-main の親）")
]
DryRunOption = Annotated[bool, typer.Option("--dry-run", help="変更を伴うコマンドを表示だけする")]


def now() -> datetime:
    return datetime.now(UTC)


def run_guarded(action) -> None:
    try:
        action()
    except DevEnvError as error:
        typer.secho(f"エラー: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error


@app.command("install")
def install(
    root: RootOption = None,
    no_start: Annotated[bool, typer.Option("--no-start", help="コンテナの起動と CA 登録を行わない")] = False,
    skip_trust: Annotated[bool, typer.Option("--skip-trust", help="Caddy CA をキーチェーンに登録しない")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """wp-wp1 / wp-wp2 を取得し、hosts・ネットワーク・Caddy を含む開発環境を構築して起動する。"""
    options = {"root": root, "no_start": no_start, "skip_trust": skip_trust}
    started = now()
    try:
        devenv.install(Runner(dry_run), resolve_root(root), start=not no_start, trust=not skip_trust)
    except DevEnvError as error:
        typer.secho(f"エラー: {error}", fg=typer.colors.RED, err=True)
        if not dry_run:
            operations.record("install", options, started, now(), exit_code=1, succeeded=False, summary=str(error))
        raise typer.Exit(1) from error
    if not dry_run:
        operations.record("install", options, started, now(), exit_code=0, succeeded=True, summary="構築しました")


@app.command("uninstall")
def uninstall(
    root: RootOption = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="確認プロンプトを省略する")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """install で導入したサイトディレクトリ・Docker リソース・hosts・CA を削除する。"""
    run_guarded(lambda: devenv.uninstall(Runner(dry_run), resolve_root(root), assume_yes=yes))


@app.command("migrate")
def migrate(
    root: RootOption = None,
    auto: Annotated[bool, typer.Option("--auto", help="自動で実行できる場合だけ移行する（git のフック用）")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="破壊的な migration の確認を省略する")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """環境を最新の環境バージョンへ移行する。"""
    code = 0
    started = now()
    # 何も適用しなかった実行は記録しないため、migration を実行したときだけ結果を受け取る
    attempts: list[tuple[int, int, str | None]] = []
    try:
        code = versioning.migrate(
            Runner(dry_run), resolve_root(root), auto=auto, assume_yes=yes,
            report=lambda before, after, error: attempts.append((before, after, error)),
        )
    except Exception as error:
        # --auto は git のフックから呼ばれるため、migration の読み込み失敗なども含めて終了コード 0 にする
        if not auto and not isinstance(error, DevEnvError):
            raise
        typer.secho(f"エラー: {error}", fg=typer.colors.RED, err=True)
        code = 0 if auto else 1
    for before, after, error in attempts:
        summary = f"{before} → {after}" + (f": {error}" if error else "")
        options = {"root": root, "auto": auto, "yes": yes}
        operations.record("migrate", options, started, now(), exit_code=code, succeeded=error is None, summary=summary)
    raise typer.Exit(code)


STATUS_COLORS = {
    health.OK: typer.colors.GREEN,
    health.WARN: typer.colors.YELLOW,
    health.FAIL: typer.colors.RED,
    health.SKIP: typer.colors.BRIGHT_BLACK,
}


@app.command("check-health")
def check_health(
    root: RootOption = None,
    as_json: Annotated[bool, typer.Option("--json", help="結果を JSON で出力する")] = False,
) -> None:
    """開発環境が正常に動いているかを、変更を加えずに確認する。"""
    started = now()
    outcomes = health.run_health(health.HealthContext(Runner(), resolve_root(root)))
    summary = health.summarize(outcomes)
    if as_json:
        typer.echo(health.to_json(outcomes))
    else:
        group = None
        for outcome in outcomes:
            if outcome.group != group:
                group = outcome.group
                typer.secho(f"\n{health.GROUPS[group]}", bold=True)
            typer.secho(f"  [{outcome.status:<4}] ", fg=STATUS_COLORS[outcome.status], nl=False)
            typer.echo(f"{outcome.title}: {outcome.message}")
            if outcome.hint and outcome.status in (health.WARN, health.FAIL):
                typer.echo(f"         → {outcome.hint}")
        typer.echo("\n" + " / ".join(f"{status} {count}" for status, count in summary.items()))
    code = 1 if summary[health.FAIL] else 0
    counts = " / ".join(f"{status} {count}" for status, count in summary.items())
    options = {"root": root, "json": as_json}
    operations.record("check-health", options, started, now(), exit_code=code, succeeded=code == 0, summary=counts)
    raise typer.Exit(code)


@app.command("version")
def version() -> None:
    """バージョンを表示する。"""
    typer.echo(__version__)
