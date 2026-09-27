import fcntl
import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .config import CADDY_CONTAINER, CADDY_SERVICE, LOCK_DIR, MAIN_DIR, MYSQL_CONTAINER, MYSQL_SERVICE, SITES, Site
from .docker import compose
from .runner import DevEnvError, Runner
from .sites import read_env

RUNNING, STOPPED, PARTIAL, STARTING, UNKNOWN = "running", "stopped", "partial", "starting", "unknown"
LABELS = {RUNNING: "起動中", STOPPED: "停止中", PARTIAL: "一部停止", STARTING: "処理中", UNKNOWN: "取得不可"}
START_TIMEOUT_SECONDS = 120
SCHEMA_NAME = re.compile(r"^[A-Za-z0-9_]+$")


class Busy(Exception):
    pass


@dataclass(frozen=True)
class SiteState:
    state: str
    detail: str = ""

    @property
    def label(self) -> str:
        return LABELS[self.state]


def inspect_containers(runner: Runner, names: list[str]) -> dict[str, dict] | None:
    """戻り値は名前ごとの docker inspect の結果。Docker に接続できなければ None。"""
    result = runner.run(["docker", "inspect", *names], check=False, mutate=False)
    try:
        items = json.loads(result.stdout or "[]")
    except ValueError:
        items = []
    # 存在しないコンテナがあっても、見つかった分の JSON は出力される
    if result.returncode != 0 and not items and "No such object" not in (result.stderr or ""):
        return None
    return {item.get("Name", "").lstrip("/"): item for item in items}


def is_running(item: dict | None) -> bool:
    return bool(item) and item.get("State", {}).get("Status") == "running"


def is_healthy(item: dict | None) -> bool:
    return is_running(item) and item.get("State", {}).get("Health", {}).get("Status") == "healthy"


def inspect(runner: Runner, site: Site) -> SiteState:
    items = inspect_containers(runner, [site.wordpress_service, MYSQL_CONTAINER])
    if items is None:
        return SiteState(UNKNOWN, "Docker に接続できません")
    if not is_running(items.get(site.wordpress_service)):
        return SiteState(STOPPED)
    if not is_healthy(items.get(MYSQL_CONTAINER)):
        return SiteState(PARTIAL, f"{MYSQL_CONTAINER} が healthy ではありません")
    return SiteState(RUNNING)


def inspect_mysql(runner: Runner) -> SiteState:
    items = inspect_containers(runner, [MYSQL_CONTAINER])
    if items is None:
        return SiteState(UNKNOWN, "Docker に接続できません")
    item = items.get(MYSQL_CONTAINER)
    if not is_running(item):
        return SiteState(STOPPED)
    return SiteState(RUNNING) if is_healthy(item) else SiteState(STARTING, f"{MYSQL_CONTAINER} が healthy ではありません")


def running_sites(runner: Runner) -> list[Site]:
    items = inspect_containers(runner, [site.wordpress_service for site in SITES]) or {}
    return [site for site in SITES if is_running(items.get(site.wordpress_service))]


def start_infra(runner: Runner, main_dir: Path = MAIN_DIR) -> None:
    compose(
        runner, "up", "-d", "--wait", "--wait-timeout", str(START_TIMEOUT_SECONDS), CADDY_SERVICE, MYSQL_SERVICE,
        cwd=main_dir, capture=True,
    )


def stop_infra(runner: Runner, main_dir: Path = MAIN_DIR) -> None:
    # -v を付けないので、共有 MySQL とサイトのボリュームは残る
    compose(runner, "down", "--remove-orphans", cwd=main_dir, capture=True)


def infra_exists(runner: Runner) -> bool:
    return bool(inspect_containers(runner, [CADDY_CONTAINER, MYSQL_CONTAINER]))


def schema_name(site: Site, root: Path) -> str:
    name = read_env(root / site.dir_name).get("WP_DB_NAME") or site.id
    if not SCHEMA_NAME.match(name):
        raise DevEnvError(f"{root / site.dir_name / '.env'} の WP_DB_NAME に使えない文字があります: {name}")
    return name


def ensure_schema(runner: Runner, site: Site, root: Path) -> None:
    name = schema_name(site, root)
    # sh の二重引用符の中でバッククォートがコマンド置換にならないようエスケープする
    sql = f"CREATE DATABASE IF NOT EXISTS \\`{name}\\`; GRANT ALL PRIVILEGES ON \\`{name}\\`.* TO '$MYSQL_USER'@'%';"
    # パスワードをホストのコマンドラインに出さないよう、コンテナの環境変数をコンテナの中で参照する
    runner.run(
        ["docker", "exec", MYSQL_CONTAINER, "sh", "-c", f'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "{sql}"'],
        capture=True,
    )


def start(runner: Runner, site: Site, root: Path, main_dir: Path = MAIN_DIR) -> None:
    if not (root / site.dir_name / ".env").exists():
        raise DevEnvError(f"{root / site.dir_name / '.env'} がありません。uv run manage.py devenv install で生成してください")
    if inspect(runner, site).state == UNKNOWN:
        raise DevEnvError("Docker に接続できません")
    compose(
        runner, "up", "-d", "--wait", "--wait-timeout", str(START_TIMEOUT_SECONDS), MYSQL_SERVICE,
        cwd=main_dir, capture=True,
    )
    ensure_schema(runner, site, root)
    compose(
        runner, "up", "-d", "--wait", "--wait-timeout", str(START_TIMEOUT_SECONDS), site.wordpress_service,
        cwd=main_dir, capture=True,
    )


def stop(runner: Runner, site: Site, root: Path | None = None, main_dir: Path = MAIN_DIR) -> None:
    if inspect(runner, site).state == UNKNOWN:
        raise DevEnvError("Docker に接続できません")
    # down はコンテナを消し、次の起動で作り直しになるので使わない。共有 MySQL は他のサイトが使うので止めない
    compose(runner, "stop", site.wordpress_service, cwd=main_dir, capture=True)


@contextmanager
def site_lock(site: Site, lock_dir: Path | None = None) -> Iterator[None]:
    """gunicorn の worker と serve をまたいで、同じサイトへの操作を 1 つに限る。"""
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
