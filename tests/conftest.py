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
        self.envs: list[dict[str, str] | None] = []
        self.responder = responder or (lambda args: (0, ""))

    def run(self, args, *, cwd=None, check=True, capture=False, mutate=True, env=None):
        self.calls.append(list(args))
        self.envs.append(env)
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
def recorded_operations(monkeypatch) -> list[dict]:
    """テストが実際の .local/db.sqlite3 に履歴を書かないよう、書き込みを記録だけにする。"""
    recorded: list[dict] = []
    monkeypatch.setattr(operations, "write", recorded.append)
    return recorded


@pytest.fixture(autouse=True)
def prepared_db(monkeypatch) -> list[bool]:
    """install のテストが実際の .local/db.sqlite3 を作らないよう、DB の準備を記録だけにする。"""
    from wp_main import devenv

    prepared: list[bool] = []
    monkeypatch.setattr(devenv, "prepare_db", lambda runner: prepared.append(runner.dry_run))
    monkeypatch.setattr(devenv, "session_running", lambda: False)
    return prepared


@pytest.fixture(autouse=True)
def isolated_session(tmp_path_factory, monkeypatch):
    """テストが実際の開発セッションの記録とログを読み書きしないよう、置き場所を一時ディレクトリにする。"""
    from wp_main import logs, session

    local = tmp_path_factory.mktemp("local")
    monkeypatch.setattr(session, "SESSION_FILE", local / "serve.pid")
    monkeypatch.setattr(session, "LOG_DIR", local / "logs")
    monkeypatch.setattr(logs, "LOG_DIR", local / "logs")
    return local
