from pathlib import Path
from typing import Annotated

import typer

from . import __version__, devenv, health
from .config import resolve_root
from .runner import DevEnvError, Runner

app = typer.Typer(
    help="wp-main: マルチリポジトリ WordPress 開発環境の管理 CLI",
    no_args_is_help=True,
    add_completion=False,
)

RootOption = Annotated[
    Path | None, typer.Option("--root", help="wp-wp1 / wp-wp2 を置くディレクトリ（既定: wp-main の親）")
]
DryRunOption = Annotated[bool, typer.Option("--dry-run", help="変更を伴うコマンドを表示だけする")]


def run_guarded(action) -> None:
    try:
        action()
    except DevEnvError as error:
        typer.secho(f"エラー: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from error


@app.command("dev-env:install")
def install(
    root: RootOption = None,
    no_start: Annotated[bool, typer.Option("--no-start", help="コンテナの起動と CA 登録を行わない")] = False,
    skip_trust: Annotated[bool, typer.Option("--skip-trust", help="Caddy CA をキーチェーンに登録しない")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """wp-wp1 / wp-wp2 を取得し、hosts・ネットワーク・Caddy を含む開発環境を構築して起動する。"""
    run_guarded(
        lambda: devenv.install(Runner(dry_run), resolve_root(root), start=not no_start, trust=not skip_trust)
    )


@app.command("dev-env:uninstall")
def uninstall(
    root: RootOption = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="確認プロンプトを省略する")] = False,
    dry_run: DryRunOption = False,
) -> None:
    """install で導入したサイトディレクトリ・Docker リソース・hosts・CA を削除する。"""
    run_guarded(lambda: devenv.uninstall(Runner(dry_run), resolve_root(root), assume_yes=yes))


STATUS_COLORS = {
    health.OK: typer.colors.GREEN,
    health.WARN: typer.colors.YELLOW,
    health.FAIL: typer.colors.RED,
    health.SKIP: typer.colors.BRIGHT_BLACK,
}


@app.command("dev-env:check-health")
def check_health(
    root: RootOption = None,
    as_json: Annotated[bool, typer.Option("--json", help="結果を JSON で出力する")] = False,
) -> None:
    """開発環境が正常に動いているかを、変更を加えずに確認する。"""
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
    if summary[health.FAIL]:
        raise typer.Exit(1)


@app.command("help")
def show_help(ctx: typer.Context) -> None:
    """コマンド一覧を表示する。"""
    typer.echo(ctx.parent.get_help())


@app.command("version")
def version() -> None:
    """バージョンを表示する。"""
    typer.echo(__version__)
