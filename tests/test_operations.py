import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wp_main import operations
from wp_main.dashboard.models import Operation
from wp_main.operations import write as real_write

START = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 27, 1, 1, tzinfo=timezone.utc)


def call(writer, **values):
    fields = {"exit_code": 0, "succeeded": True, "summary": "4 → 5"} | values
    return operations.record("migrate", {"auto": True, "root": Path("/work")}, START, END, writer=writer, **fields)


def test_record_builds_payload():
    written = []
    assert call(written.append)
    assert written == [{
        "command": "migrate", "options": {"auto": True, "root": "/work"},
        "started_at": START, "finished_at": END,
        "exit_code": 0, "succeeded": True, "summary": "4 → 5",
    }]


def test_record_failure_only_warns(capsys):
    def broken(payload):
        raise OSError("attempt to write a readonly database")

    assert call(broken) is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "操作履歴を記録できませんでした: attempt to write a readonly database" in captured.err


@pytest.mark.django_db(transaction=True)
def test_record_writes_to_db():
    assert call(real_write, summary="x" * 600)
    [operation] = Operation.objects.all()
    assert operation.command == "migrate" and operation.options == {"auto": True, "root": "/work"}
    assert operation.finished_at == END and len(operation.summary) == 500


@pytest.mark.django_db(transaction=True)
def test_record_prunes(monkeypatch):
    monkeypatch.setattr("wp_main.dashboard.models.MAX_OPERATIONS", 2)
    for _ in range(3):
        call(real_write)
    assert Operation.objects.count() == 2


def test_write_creates_missing_db(tmp_path):
    # 実際の .local を触らないよう、別のプロセスで DB の場所を差し替えて確かめる
    db = tmp_path / "db.sqlite3"
    script = (
        "import django; django.setup();"
        "from datetime import datetime, timezone; from wp_main.operations import write;"
        "from wp_main.dashboard.models import Operation;"
        "now = datetime.now(timezone.utc);"
        "write({'command': 'check-health', 'options': {}, 'started_at': now, 'finished_at': now,"
        " 'exit_code': 0, 'succeeded': True, 'summary': 'OK 1'});"
        "print(Operation.objects.count())"
    )
    env = os.environ | {"DJANGO_SETTINGS_MODULE": "wp_main.settings", "DJANGO_DB_PATH": str(db)}
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1" and db.exists()
