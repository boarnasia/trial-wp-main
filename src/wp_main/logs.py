"""serve logs: ホストのプロセスのログファイルと、共有インフラ・サイトのコンテナのログを 1 本にまとめて表示する。"""
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from . import power, processes
from .config import CADDY_CONTAINER, CADDY_SERVICE, LOG_DIR, MAIN_DIR, MYSQL_CONTAINER, MYSQL_SERVICE, SITES
from .docker import compose_env
from .runner import DevEnvError, Runner

FOLLOW_POLL_SECONDS = 0.3
SERVE_NAME = "serve"


@dataclass(frozen=True)
class Source:
    name: str
    log_file: Path | None = None
    service: str = ""
    container: str = ""


def sources(log_dir: Path | None = None) -> dict[str, Source]:
    log_dir = log_dir or LOG_DIR
    host = [SERVE_NAME, *(process.name for process in processes.host_processes(0, MAIN_DIR))]
    found = {name: Source(name, log_file=log_dir / f"{name}.log") for name in host}
    found[CADDY_SERVICE] = Source(CADDY_SERVICE, service=CADDY_SERVICE, container=CADDY_CONTAINER)
    found[MYSQL_SERVICE] = Source(MYSQL_SERVICE, service=MYSQL_SERVICE, container=MYSQL_CONTAINER)
    for site in SITES:
        found[site.id] = Source(site.id, service=site.wordpress_service, container=site.wordpress_service)
    return found


def select(names: list[str], runner: Runner, log_dir: Path | None = None) -> list[Source]:
    known = sources(log_dir)
    unknown = [name for name in names if name not in known]
    if unknown:
        raise DevEnvError(f"存在しない名前です: {', '.join(unknown)}（指定できるもの: {', '.join(known)}）")
    if names:
        return [known[name] for name in dict.fromkeys(names)]
    # 名前を省いたときは、今読めるものだけに絞る
    containers = [source.container for source in known.values() if source.container]
    running = power.inspect_containers(runner, containers) or {}
    return [
        source for source in known.values()
        if (source.log_file and source.log_file.exists()) or power.is_running(running.get(source.container))
    ]


def last_lines(path: Path, tail: int | None) -> list[str]:
    if not path.exists():
        return []
    with open(path, errors="replace") as handle:
        return list(deque(handle, maxlen=tail) if tail is not None else handle)


def compose_logs_command(source: Source, follow: bool, tail: int | None) -> list[str]:
    return [
        "docker", "compose", "logs", "--no-log-prefix",
        *(["-f"] if follow else []),
        *(["--tail", str(tail)] if tail is not None else []),
        source.service,
    ]


def open_compose_logs(source: Source, follow: bool, tail: int | None) -> subprocess.Popen:
    return subprocess.Popen(
        compose_logs_command(source, follow, tail),
        cwd=MAIN_DIR,
        env=os.environ | compose_env(MAIN_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )


def follow_file(path: Path, tail: int | None, emit: Callable[[str], None], stop: threading.Event) -> None:
    handle, inode = None, None
    if path.exists():
        # 既存の行を読み終えた位置から追うので、読み出しと追跡の間の行を取りこぼさない
        handle = open(path, errors="replace")
        inode = os.fstat(handle.fileno()).st_ino
        for line in deque(handle, maxlen=tail):
            emit(line)
    while not stop.is_set():
        if handle is None:
            if not path.exists():
                stop.wait(FOLLOW_POLL_SECONDS)
                continue
            handle = open(path, errors="replace")
            inode = os.fstat(handle.fileno()).st_ino
        line = handle.readline()
        if line:
            emit(line)
            continue
        try:
            replaced = os.stat(path).st_ino != inode
        except FileNotFoundError:
            replaced = True
        if replaced:
            # 次の serve up で置き換えられたので、新しいファイルを先頭から読む
            handle.close()
            handle = None
            continue
        stop.wait(FOLLOW_POLL_SECONDS)
    if handle:
        handle.close()


def show(
    selected: Iterable[Source],
    *,
    follow: bool,
    tail: int | None,
    write: Callable[[str], None] | None = None,
    stop: threading.Event | None = None,
) -> None:
    selected = list(selected)
    if not selected:
        return
    width = max(len(source.name) for source in selected)
    lock = threading.Lock()
    out = write or (lambda text: (sys.stdout.write(text), sys.stdout.flush()))

    def emitter(name: str) -> Callable[[str], None]:
        def emit(line: str) -> None:
            with lock:
                out(f"{name:<{width}} | {line.rstrip()}\n")

        return emit

    if not follow:
        for source in selected:
            emit = emitter(source.name)
            if source.log_file:
                for line in last_lines(source.log_file, tail):
                    emit(line)
            else:
                child = open_compose_logs(source, False, tail)
                for line in child.stdout:
                    emit(line)
                child.wait()
        return

    stop = stop or threading.Event()
    children: list[subprocess.Popen] = []
    threads: list[threading.Thread] = []
    for source in selected:
        emit = emitter(source.name)
        if source.log_file:
            target, args = follow_file, (source.log_file, tail, emit, stop)
        else:
            child = open_compose_logs(source, True, tail)
            children.append(child)
            target, args = (lambda stream, emit: [emit(line) for line in stream]), (child.stdout, emit)
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        threads.append(thread)
    # SIGTERM でも docker compose logs の子を残さずに終える
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
    try:
        while not stop.wait(FOLLOW_POLL_SECONDS):
            pass
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(5)
            except subprocess.TimeoutExpired:
                child.kill()
        deadline = time.monotonic() + 1
        for thread in threads:
            thread.join(max(0.0, deadline - time.monotonic()))
