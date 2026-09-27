import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from django.core.management import ManagementUtility

from wp_main import operations
from wp_main.runner import DevEnvError, Runner


class FakeRunner(Runner):
    """実際のコマンドは実行せず、呼び出しを記録して responder の結果を返す。"""

    def __init__(self, responder: Callable[[list[str]], tuple[int, str]] | None = None, dry_run=False):
        super().__init__(dry_run=dry_run)
        self.calls: list[list[str]] = []
        self.responder = responder or (lambda args: (0, ""))

    def run(self, args, *, cwd=None, check=True, capture=False, mutate=True):
        self.calls.append(list(args))
        code, out = (0, "") if (mutate and self.dry_run) else self.responder(list(args))
        if check and code != 0:
            raise DevEnvError(f"failed: {args}")
        return subprocess.CompletedProcess(args, code, out, "")

    def mutating(self, prefix: list[str]) -> list[list[str]]:
        return [call for call in self.calls if call[: len(prefix)] == prefix]


@pytest.fixture
def fake_runner():
    return FakeRunner


@dataclass
class ManageResult:
    exit_code: int
    stdout: str
    stderr: str


@pytest.fixture
def manage(capsys):
    """`manage.py` と同じ経路でコマンドを実行し、終了コードと出力を返す。"""

    def run(*args: str) -> ManageResult:
        capsys.readouterr()
        try:
            ManagementUtility(["manage.py", *args]).execute()
            code = 0
        except SystemExit as exit:
            code = exit.code if isinstance(exit.code, int) else (0 if exit.code is None else 1)
        captured = capsys.readouterr()
        return ManageResult(code, captured.out, captured.err)

    return run


@pytest.fixture(autouse=True)
def sent_operations(monkeypatch) -> list[dict]:
    """テストから実際のダッシュボードへ履歴を送らないよう、送信を記録だけにする。"""
    sent: list[dict] = []
    monkeypatch.setattr(operations, "send", sent.append)
    return sent
