import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import typer

from .config import MAIN_DIR

STOP_TIMEOUT_SECONDS = 10
POLL_SECONDS = 0.2
READY_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class HostProcess:
    name: str
    command: list[str]
    cwd: Path = MAIN_DIR
    env: dict[str, str] = field(default_factory=dict)


def host_processes(port: int, root: Path) -> list[HostProcess]:
    """serve が起動するプロセス。vite などはここに加える。"""
    return [
        HostProcess(
            "dashboard",
            [
                sys.executable, "-m", "gunicorn", "wp_main.wsgi:application",
                "--bind", f"127.0.0.1:{port}",
                "--workers", "2",
                # サイトの起動は最大 120 秒待つため、既定の 30 秒では worker が殺される
                "--timeout", "150",
                "--access-logfile", "-",
            ],
            env={"DJANGO_SETTINGS_MODULE": "wp_main.settings", "WP_MAIN_ROOT": str(root)},
        ),
    ]


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@dataclass
class Exited:
    name: str
    code: int


def supervise(
    processes: list[HostProcess],
    *,
    stop: threading.Event | None = None,
    echo: Callable[[str], None] = typer.echo,
    log_dir: Path | None = None,
    ready: Callable[[], bool] | None = None,
    on_ready: Callable[[], None] | None = None,
    ready_timeout: float = READY_TIMEOUT_SECONDS,
) -> int:
    """全プロセスを起動し、停止の合図か 1 つの終了で全体を止める。正常な停止なら 0 を返す。

    stop を渡した場合、シグナルの扱いは呼び出し側が受け持つ。ready を渡した場合、ready_timeout 秒以内に
    真にならなければ失敗として全体を止め、真になったら on_ready を 1 回呼ぶ。
    """
    own_signals = stop is None
    stop = stop or threading.Event()
    width = max(len(process.name) for process in processes)
    children: list[tuple[HostProcess, subprocess.Popen]] = []
    pumps: list[threading.Thread] = []
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    def pump(name: str, stream) -> None:
        log = open(log_dir / f"{name}.log", "a", buffering=1) if log_dir else None
        try:
            for line in stream:
                if log:
                    log.write(line)
                echo(f"{name:<{width}} | {line.rstrip()}")
        finally:
            if log:
                log.close()

    def request_stop(signum, frame) -> None:
        stop.set()

    previous = {}
    if own_signals and threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, request_stop)

    exited: Exited | None = None
    unready = False
    try:
        for process in processes:
            child = subprocess.Popen(
                process.command,
                cwd=process.cwd,
                env=os.environ | process.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # Ctrl-C を子に直接届けず、ここから順に止める
                start_new_session=True,
            )
            children.append((process, child))
            thread = threading.Thread(target=pump, args=(process.name, child.stdout), daemon=True)
            thread.start()
            pumps.append(thread)

        deadline = time.monotonic() + ready_timeout
        waiting = ready is not None
        while exited is None and not stop.wait(POLL_SECONDS):
            for process, child in children:
                if child.poll() is not None:
                    exited = Exited(process.name, child.returncode)
                    break
            if exited is None and waiting:
                if ready():
                    waiting = False
                    if on_ready:
                        on_ready()
                elif time.monotonic() > deadline:
                    unready = True
                    break
    finally:
        for _, child in children:
            if child.poll() is None:
                child.terminate()
        for _, child in children:
            try:
                child.wait(STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for thread in pumps:
            thread.join(1)
        for signum, handler in previous.items():
            signal.signal(signum, handler)

    if exited is not None:
        typer.secho(f"{exited.name} が終了しました (exit {exited.code})。他のプロセスも停止しました", fg=typer.colors.RED, err=True)
        return 1
    if unready:
        typer.secho(f"{int(ready_timeout)} 秒以内に応答しませんでした。プロセスを停止しました", fg=typer.colors.RED, err=True)
        return 1
    return 0
