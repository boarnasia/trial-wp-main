from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import typer
from django.core.management import call_command
from django.db import transaction


def write(payload: dict) -> None:
    from .dashboard.models import Operation

    # ダッシュボードを一度も起動していない環境でも記録できるよう、スキーマをここで最新にする
    call_command("migrate", verbosity=0, interactive=False)
    summary_limit = Operation._meta.get_field("summary").max_length
    with transaction.atomic():
        Operation.objects.create(**(payload | {"summary": payload["summary"][:summary_limit]}))
        Operation.prune()


def record(
    command: str,
    options: dict,
    started_at: datetime,
    finished_at: datetime,
    *,
    exit_code: int,
    succeeded: bool,
    summary: str,
    writer: Callable[[dict], None] | None = None,
) -> bool:
    """操作を記録する。失敗しても警告を出すだけで、呼び出し元の結果は変えない。"""
    payload = {
        "command": command,
        "options": {key: str(value) if isinstance(value, Path) else value for key, value in options.items()},
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "succeeded": succeeded,
        "summary": summary,
    }
    try:
        (writer or write)(payload)
    except Exception as error:  # 記録は best effort。どんな失敗でも本来のコマンドを止めない
        typer.secho(f"警告: 操作履歴を記録できませんでした: {error}", fg=typer.colors.YELLOW, err=True)
        return False
    return True
