import importlib
import pkgutil
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import typer

from .devenv import migrations as default_package
from . import trust
from .config import MAIN_DIR, SITES, Site
from .runner import DevEnvError, Runner

BASE_VERSION = 1
MODULE_NAME = re.compile(r"^m(\d{4})_[a-z0-9_]+$")
MIGRATE_COMMAND = "uv run manage.py devenv migrate"


@dataclass
class MigrationContext:
    runner: Runner
    root: Path
    main_dir: Path
    sites: tuple[Site, ...]


def discover(package: ModuleType = default_package) -> list[ModuleType]:
    found = []
    for info in pkgutil.iter_modules(package.__path__):
        match = MODULE_NAME.match(info.name)
        if not match:
            raise DevEnvError(f"migration のファイル名が不正です: {info.name}（mNNNN_<名前>.py）")
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        if getattr(module, "VERSION", None) != int(match.group(1)):
            raise DevEnvError(f"{info.name} の VERSION がファイル名の番号と一致しません")
        found.append(module)
    found.sort(key=lambda module: module.VERSION)
    expected = list(range(BASE_VERSION + 1, BASE_VERSION + 1 + len(found)))
    actual = [module.VERSION for module in found]
    if actual != expected:
        raise DevEnvError(f"migration の番号は {BASE_VERSION + 1} からの連番にしてください（現在: {actual}）")
    return found


def latest_version(found: list[ModuleType]) -> int:
    return found[-1].VERSION if found else BASE_VERSION


def latest() -> int:
    return latest_version(discover())


def installed_version(root: Path) -> int | None:
    version = trust.load_state().get("env_version")
    if version is not None:
        return int(version)
    # env_version の導入前に作られた環境は、サイトのディレクトリがあることで判別する
    if any((root / site.dir_name).exists() for site in SITES):
        return BASE_VERSION
    return None


def outdated_message(root: Path) -> str | None:
    installed, newest = installed_version(root), latest()
    if installed is None or installed >= newest:
        return None
    return f"環境バージョンが古くなっています（{installed} → {newest}）。{MIGRATE_COMMAND} を実行してください"


def record_latest() -> None:
    trust.update_state(env_version=latest())


def describe(module: ModuleType) -> str:
    flags = [label for flag, label in ((module.REQUIRES_SUDO, "sudo"), (module.DESTRUCTIVE, "破壊的")) if flag]
    return f"{module.VERSION}: {module.DESCRIPTION}" + (f" [{', '.join(flags)}]" if flags else "")


def migrate(
    runner: Runner,
    root: Path,
    *,
    auto: bool = False,
    assume_yes: bool = False,
    package: ModuleType = default_package,
    main_dir: Path = MAIN_DIR,
    is_tty: Callable[[], bool] = sys.stdin.isatty,
) -> int:
    """終了コードを返す。--auto は git のフックから呼ばれるため、pull を妨げないよう常に 0 を返す。"""
    failure = 0 if auto else 1
    found = discover(package)
    newest = latest_version(found)
    installed = installed_version(root)

    if installed is None:
        typer.echo("環境が導入されていません。uv run manage.py devenv install を実行してください")
        return failure
    if installed == newest:
        typer.echo(f"環境バージョン {installed} は最新です")
        return 0
    if installed > newest:
        typer.echo(
            f"環境バージョン {installed} はコードの最新 {newest} より新しいため、移行できません。"
            "wp-main を git pull してコードを更新してください"
        )
        return failure

    pending = [module for module in found if module.VERSION > installed]
    typer.echo(f"環境バージョン {installed} → {newest}。未適用の migration:")
    for module in pending:
        typer.echo(f"  {describe(module)}")

    if auto:
        reasons = []
        if any(module.REQUIRES_SUDO for module in pending):
            reasons.append("sudo が必要な migration があります")
        if any(module.DESTRUCTIVE for module in pending):
            reasons.append("データを失う migration があります")
        if not runner.ok(["docker", "info"]):
            reasons.append("Docker に接続できません")
        if reasons:
            typer.secho(
                f"自動では移行しません（{'、'.join(reasons)}）。端末で {MIGRATE_COMMAND} を実行してください",
                fg=typer.colors.YELLOW,
            )
            return 0
    else:
        destructive = [module for module in pending if module.DESTRUCTIVE]
        for module in destructive:
            typer.secho(f"  {module.VERSION} で失われるもの: {module.LOSES}", fg=typer.colors.YELLOW)
        if destructive and not assume_yes and not typer.confirm("移行を実行しますか？", default=False):
            typer.echo("中止しました。")
            return 1
        if any(module.REQUIRES_SUDO for module in pending) and not is_tty():
            typer.secho(
                f"sudo が必要な migration があります。パスワードを入力できる端末で {MIGRATE_COMMAND} を実行してください",
                fg=typer.colors.RED,
            )
            return 1

    if runner.dry_run:
        typer.echo("[dry-run] 上記の migration を実行します（環境バージョンは更新しません）")
        return 0

    context = MigrationContext(runner, root, main_dir, SITES)
    for module in pending:
        typer.secho(f"==> migration {describe(module)}", fg=typer.colors.CYAN, bold=True)
        try:
            module.up(context)
        except Exception as error:
            typer.secho(
                f"migration {module.VERSION} ({module.__name__}) が失敗しました: {error}\n"
                f"環境バージョンは {trust.load_state().get('env_version', installed)} のままです",
                fg=typer.colors.RED,
            )
            return failure
        trust.update_state(env_version=module.VERSION)
    typer.secho(f"環境バージョン {newest} に移行しました", fg=typer.colors.GREEN, bold=True)
    return 0
