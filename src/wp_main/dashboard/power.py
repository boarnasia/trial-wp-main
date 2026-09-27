import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..config import LOCK_DIR, MAIN_DIR, Site
from ..docker import compose
from ..runner import DevEnvError, Runner

RUNNING, STOPPED, PARTIAL, UNKNOWN = "running", "stopped", "partial", "unknown"
LABELS = {RUNNING: "起動中", STOPPED: "停止中", PARTIAL: "一部停止", UNKNOWN: "取得不可"}
MAIN_PROJECT = "wp-main"
PROJECT_LABEL = "com.docker.compose.project"
START_TIMEOUT_SECONDS = 120


class Busy(Exception):
    pass


@dataclass(frozen=True)
class SiteState:
    state: str
    # 操作する Compose プロジェクトのディレクトリ
    project_dir: Path
    detail: str = ""

    @property
    def label(self) -> str:
        return LABELS[self.state]


def containers(site: Site) -> list[str]:
    return [site.wordpress_service, f"{site.id}-db"]


def inspect(runner: Runner, site: Site, root: Path, main_dir: Path = MAIN_DIR) -> SiteState:
    result = runner.run(["docker", "inspect", *containers(site)], check=False, mutate=False)
    try:
        items = json.loads(result.stdout or "[]")
    except ValueError:
        items = []
    # 存在しないコンテナがあっても、見つかった分の JSON は出力される
    if result.returncode != 0 and not items and "No such object" not in (result.stderr or ""):
        detail = (result.stderr or "").strip().splitlines()
        return SiteState(UNKNOWN, main_dir, detail[-1] if detail else "Docker に接続できません")
    projects = {item.get("Config", {}).get("Labels", {}).get(PROJECT_LABEL, "") for item in items}
    solo = any(project and project != MAIN_PROJECT for project in projects)
    project_dir = root / site.dir_name if solo else main_dir
    running = sum(1 for item in items if item.get("State", {}).get("Status") == "running")
    if running == len(containers(site)):
        return SiteState(RUNNING, project_dir)
    return SiteState(PARTIAL if running else STOPPED, project_dir)


def start(runner: Runner, site: Site, root: Path, main_dir: Path = MAIN_DIR) -> None:
    if not (root / site.dir_name / ".env").exists():
        raise DevEnvError(f"{root / site.dir_name / '.env'} がありません。uv run manage.py devenv install で生成してください")
    state = inspect(runner, site, root, main_dir)
    if state.state == UNKNOWN:
        raise DevEnvError(state.detail)
    # depends_on により DB も起動し、healthy になるまで待つ
    compose(
        runner, "up", "-d", "--wait", "--wait-timeout", str(START_TIMEOUT_SECONDS), site.wordpress_service,
        cwd=state.project_dir, capture=True,
    )


def stop(runner: Runner, site: Site, root: Path, main_dir: Path = MAIN_DIR) -> None:
    state = inspect(runner, site, root, main_dir)
    if state.state == UNKNOWN:
        raise DevEnvError(state.detail)
    # down はコンテナを消し、単体起動との切り替えを分かりにくくするので使わない
    compose(runner, "stop", *containers(site), cwd=state.project_dir, capture=True)


@contextmanager
def site_lock(site: Site, lock_dir: Path | None = None) -> Iterator[None]:
    """gunicorn の worker をまたいで、同じサイトへの操作を 1 つに限る。"""
    lock_dir = lock_dir or LOCK_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    with open(lock_dir / f"site-{site.id}.lock", "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Busy(site.id) from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def is_busy(site: Site, lock_dir: Path | None = None) -> bool:
    try:
        with site_lock(site, lock_dir):
            return False
    except Busy:
        return True
