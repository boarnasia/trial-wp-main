import socket
import time
from collections.abc import Callable
from pathlib import Path

from .config import MAIN_DIR, NETWORK, SITES
from .runner import DevEnvError, Runner


def compose_env(main_dir: Path) -> dict[str, str]:
    # include の env_file はファイルがないとプロジェクト全体を読めなくするため、.env のないサイトは空のファイルに向ける
    return {
        site.env_file_variable: "/dev/null"
        for site in SITES
        if not (main_dir.parent / site.dir_name / ".env").exists()
    }


def compose(runner: Runner, *args: str, cwd: Path = MAIN_DIR, **kwargs):
    return runner.run(["docker", "compose", *args], cwd=cwd, env=compose_env(cwd) or None, **kwargs)


def ensure_network(runner: Runner) -> bool:
    if runner.ok(["docker", "network", "inspect", NETWORK]):
        return False
    runner.run(["docker", "network", "create", NETWORK])
    return True


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def caddy_running(runner: Runner) -> bool:
    result = compose(runner, "ps", "--status", "running", "-q", "caddy", check=False, mutate=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def check_ports(
    runner: Runner, ports: tuple[int, ...], is_free: Callable[[int], bool] = port_is_free
) -> None:
    # 再実行時は自分の Caddy が使用中なので検査しない
    if caddy_running(runner):
        return
    busy = [port for port in ports if not is_free(port)]
    if not busy:
        return
    holders = runner.run(
        ["lsof", "-nP", *(f"-iTCP:{port}" for port in busy), "-sTCP:LISTEN"],
        check=False,
        mutate=False,
    ).stdout.strip()
    raise DevEnvError(
        f"ポート {', '.join(map(str, busy))} が使用中です。停止してから再実行してください。"
        + (f"\n{holders}" if holders else "")
    )


def wait_for(check: Callable[[], bool], what: str, timeout: float = 120, interval: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(interval)
    raise DevEnvError(f"{what} を {int(timeout)} 秒待ちましたが完了しませんでした")
