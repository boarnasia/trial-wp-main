"""開発セッション: serve の開始から終了までに行う、共有インフラとサイトの起動・停止。"""
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import typer

from . import operations, power
from .config import SITES, Site
from .runner import DevEnvError, Runner

ALL = "all"
VIA = "serve"


def resolve_sites(value: str | None) -> list[Site]:
    if not value:
        return []
    names = [name.strip() for name in value.split(",") if name.strip()]
    if ALL in names:
        return list(SITES)
    known = {site.id: site for site in SITES}
    unknown = [name for name in names if name not in known]
    if unknown:
        choices = ", ".join([*known, ALL])
        raise DevEnvError(f"存在しないサイトです: {', '.join(unknown)}（指定できるもの: {choices}）")
    # 重複した指定は 1 回だけ起動する
    return [known[name] for name in dict.fromkeys(names)]


def now() -> datetime:
    return datetime.now(UTC)


def operate(runner: Runner, site: Site, root: Path, action: str, echo: Callable[[str], None]) -> bool:
    run, label = (power.start, "起動") if action == "start" else (power.stop, "停止")
    started = now()
    try:
        with power.site_lock(site):
            run(runner, site, root)
    except power.Busy:
        echo(f"{site.id}: 別の操作を実行中のため{label}しませんでした")
        return False
    except DevEnvError as error:
        summary = f"{site.id} の{label}に失敗しました: {error}"
        typer.secho(summary, fg=typer.colors.RED, err=True)
        operations.record(f"site-{action}", {"site": site.id, "via": VIA}, started, now(),
                          exit_code=1, succeeded=False, summary=summary)
        return False
    summary = f"{site.id} を{label}しました"
    echo(summary)
    operations.record(f"site-{action}", {"site": site.id, "via": VIA}, started, now(),
                      exit_code=0, succeeded=True, summary=summary)
    return True


def begin(runner: Runner, sites: list[Site], root: Path, echo: Callable[[str], None] = typer.echo) -> None:
    """共有インフラを起動できなければ DevEnvError。サイトの失敗は表示と記録だけにして続ける。"""
    echo("共有インフラ（プロキシ・MySQL）を起動します")
    power.start_infra(runner)
    for site in sites:
        echo(f"{site.id} を起動します")
        operate(runner, site, root, "start", echo)


def end(runner: Runner, root: Path, echo: Callable[[str], None] = typer.echo) -> None:
    # セッション中にダッシュボードから起動したサイトも含め、動いているものをすべて止める
    for site in power.running_sites(runner):
        echo(f"{site.id} を停止します")
        operate(runner, site, root, "stop", echo)
