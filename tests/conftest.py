import subprocess
from collections.abc import Callable

import pytest

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
