import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer


class DevEnvError(Exception):
    pass


@dataclass
class Runner:
    dry_run: bool = False

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        check: bool = True,
        capture: bool = False,
        mutate: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """mutate=False の読み取り系コマンドは dry-run でも実行し、後続の判定に使う。"""
        location = f" (in {cwd})" if cwd else ""
        if mutate:
            prefix = "[dry-run] " if self.dry_run else "$ "
            typer.secho(f"{prefix}{shlex.join(args)}{location}", fg=typer.colors.BRIGHT_BLACK)
            if self.dry_run:
                return subprocess.CompletedProcess(args, 0, "", "")
        result = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            capture_output=capture or not mutate,
            env={**os.environ, **env} if env else None,
        )
        if check and result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            raise DevEnvError(
                f"コマンドが失敗しました (exit {result.returncode}): {shlex.join(args)}"
                + (f"\n  {detail[-1]}" if detail else "")
            )
        return result

    def ok(self, args: list[str], *, cwd: Path | None = None) -> bool:
        return self.run(args, cwd=cwd, check=False, mutate=False).returncode == 0
