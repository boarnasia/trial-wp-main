"""開発セッション: serve up の開始から終了までに行う、共有インフラとサイトの起動・停止と、その記録。"""
import fcntl
import json
import os
import signal
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import typer

from . import operations, power, processes
from .config import DASHBOARD_DOMAIN, LOG_DIR, SESSION_FILE, SITES, Site
from .runner import DevEnvError, Runner

ALL = "all"
VIA = "serve"
STARTING, READY = "starting", "ready"
SERVE_LOG = "serve.log"
END_TIMEOUT_SECONDS = 300
KILL_WAIT_SECONDS = 10
POLL_SECONDS = 0.2


@dataclass(frozen=True)
class Info:
    pid: int
    state: str = STARTING
    failed: tuple[str, ...] = ()


class Running(Exception):
    def __init__(self, info: "Info"):
        super().__init__(f"開発セッション（PID {info.pid}）が動いています")
        self.info = info


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


def session_file(path: Path | None) -> Path:
    return path or SESSION_FILE


def read_info(handle) -> Info:
    handle.seek(0)
    try:
        data = json.loads(handle.read() or "{}")
    except ValueError:
        data = {}
    return Info(int(data.get("pid", 0)), data.get("state", STARTING), tuple(data.get("failed", ())))


def status(path: Path | None = None) -> Info | None:
    """開発セッションが動いていればその記録を、動いていなければ None を返す。ファイルは書き換えない。"""
    try:
        handle = open(session_file(path))
    except FileNotFoundError:
        return None
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return read_info(handle)
        fcntl.flock(handle, fcntl.LOCK_UN)
        return None


def is_running(path: Path | None = None) -> bool:
    return status(path) is not None


class Holder:
    def __init__(self, handle):
        self.handle = handle

    def write(self, state: str, failed: list[str] | tuple[str, ...] = ()) -> None:
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(json.dumps({"pid": os.getpid(), "state": state, "failed": list(failed)}))
        self.handle.flush()


@contextmanager
def hold(path: Path | None = None) -> Iterator[Holder]:
    """開発セッションの間、記録のファイルの排他ロックを持つ。既に持たれていれば Running。"""
    path = session_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        handle = open(path, "a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            info = read_info(handle)
            handle.close()
            raise Running(info) from None
        # ロックを取る直前に前の持ち主が消したファイルなら、同じパスに作り直したファイルで取り直す
        try:
            current = os.stat(path).st_ino == os.fstat(handle.fileno()).st_ino
        except FileNotFoundError:
            current = False
        if current:
            break
        handle.close()
    holder = Holder(handle)
    holder.write(STARTING)
    try:
        yield holder
    finally:
        # ロックを放す前に消し、放した瞬間に古い内容が読まれないようにする
        path.unlink(missing_ok=True)
        handle.close()


def clear_stale(path: Path | None = None) -> bool:
    path = session_file(path)
    try:
        handle = open(path)
    except FileNotFoundError:
        return False
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        path.unlink(missing_ok=True)
        return True


def wait_until_ended(path: Path | None, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_running(path):
            return True
        time.sleep(POLL_SECONDS)
    return not is_running(path)


def request_end(
    signum: int, path: Path | None = None, timeout: float = END_TIMEOUT_SECONDS, *, kill: bool = False
) -> Info | None:
    """動いている開発セッションにシグナルで終了を頼み、終わるまで待つ。セッションがなければ None。"""
    info = status(path)
    if info is None:
        return None
    try:
        os.kill(info.pid, signum)
    except ProcessLookupError:
        pass
    if wait_until_ended(path, timeout):
        return info
    if not kill:
        raise DevEnvError(f"開発セッション（PID {info.pid}）が {int(timeout)} 秒以内に終わりませんでした")
    typer.secho(f"開発セッション（PID {info.pid}）が {int(timeout)} 秒以内に終わらないため、強制終了します", fg=typer.colors.YELLOW, err=True)
    try:
        os.kill(info.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    wait_until_ended(path, KILL_WAIT_SECONDS)
    return info


def rotate_logs(log_dir: Path | None = None) -> None:
    log_dir = log_dir or LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    for log in log_dir.glob("*.log"):
        log.replace(log.with_name(f"{log.name}.1"))


def tee(path: Path) -> Callable[[str], None]:
    def echo(line: str) -> None:
        typer.echo(line)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as log:
            log.write(f"{line}\n")

    return echo


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
        echo(summary)
        operations.record(f"site-{action}", {"site": site.id, "via": VIA}, started, now(),
                          exit_code=1, succeeded=False, summary=summary)
        return False
    summary = f"{site.id} を{label}しました"
    echo(summary)
    operations.record(f"site-{action}", {"site": site.id, "via": VIA}, started, now(),
                      exit_code=0, succeeded=True, summary=summary)
    return True


def begin(runner: Runner, sites: list[Site], root: Path, echo: Callable[[str], None] = typer.echo) -> list[str]:
    """起動できなかったサイトの ID を返す。共有インフラを起動できなければ DevEnvError。"""
    echo("共有インフラ（プロキシ・MySQL）を起動します")
    power.start_infra(runner)
    failed = []
    for site in sites:
        echo(f"{site.id} を起動します")
        if not operate(runner, site, root, "start", echo):
            failed.append(site.id)
    return failed


def stop_infra(runner: Runner, echo: Callable[[str], None]) -> bool:
    echo("共有インフラ（プロキシ・MySQL）を停止します")
    try:
        power.stop_infra(runner)
    except DevEnvError as error:
        echo(f"共有インフラの停止に失敗しました: {error}")
        return False
    return True


def end(runner: Runner, root: Path, echo: Callable[[str], None] = typer.echo, *, infra: bool = True) -> None:
    # セッション中にダッシュボードから起動したサイトも含め、動いているものをすべて止める
    for site in power.running_sites(runner):
        echo(f"{site.id} を停止します")
        operate(runner, site, root, "stop", echo)
    if infra:
        stop_infra(runner, echo)


def supervise_session(
    runner: Runner,
    sites: list[Site],
    root: Path,
    port: int,
    *,
    prepare: Callable[[], None],
    terminal: bool,
    session_path: Path | None = None,
    log_dir: Path | None = None,
) -> int:
    """開発セッションを監督する本体。前面では端末に、デタッチでは標準出力（serve.log）に経過を出す。"""
    log_dir = log_dir or LOG_DIR
    echo = tee(log_dir / SERVE_LOG) if terminal else typer.echo
    stop, handover = threading.Event(), threading.Event()

    def on_signal(signum, frame) -> None:
        # SIGUSR1 は次の serve up への入れ替えなので、共有インフラを止めずに終える
        if signum == signal.SIGUSR1:
            handover.set()
        stop.set()

    previous = {signum: signal.signal(signum, on_signal) for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGUSR1)}
    try:
        with hold(session_path) as holder:
            try:
                prepare()
            except Exception as error:
                echo(f"DB を準備できません: {error}")
                return 1
            try:
                failed = begin(runner, sites, root, echo)
            except DevEnvError as error:
                echo(f"共有インフラを起動できません: {error}")
                stop_infra(runner, echo)
                return 1

            def on_ready() -> None:
                holder.write(READY, failed)
                echo(f"https://{DASHBOARD_DOMAIN}/ (127.0.0.1:{port}) で開発セッションを始めました")

            code = 1
            try:
                code = processes.supervise(
                    processes.host_processes(port, root),
                    stop=stop,
                    echo=typer.echo if terminal else (lambda line: None),
                    log_dir=log_dir,
                    ready=lambda: processes.port_in_use(port),
                    on_ready=on_ready,
                )
            finally:
                end(runner, root, echo, infra=not handover.is_set())
            return code
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
