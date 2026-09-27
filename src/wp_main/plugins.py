import fcntl
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .config import LOCK_DIR, MAIN_DIR, Site
from .docker import compose
from .runner import Runner

OK, NG, UNKNOWN = "ok", "ng", "unknown"
LISTED_STATUSES = ("active", "inactive", "must-use")
# must-use は wordpress.org のプラグインではないことが多いため問い合わせない
QUERIED_STATUSES = ("active", "inactive")
API_URL = "https://api.wordpress.org/plugins/info/1.2/"
API_TIMEOUT_SECONDS = 10
NOT_INSTALLED_HINT = "WordPress のファイルがありません。一度サイトを起動してから再取得してください"
VERSION = re.compile(r"\d+(?:\.\d+)*")


class Busy(Exception):
    pass


@dataclass(frozen=True)
class InstalledPlugin:
    slug: str
    title: str
    version: str
    status: str


@dataclass(frozen=True)
class SiteResult:
    wp_version: str | None
    plugins: tuple[InstalledPlugin, ...]
    error: str | None = None


@dataclass(frozen=True)
class OrgInfo:
    """wordpress.org の結果。found が False なら登録がない。"""

    found: bool
    name: str = ""
    requires: str = ""
    tested: str = ""


def parse_version(value: str | None) -> tuple[int, ...] | None:
    match = VERSION.match(value or "")
    return tuple(int(part) for part in match.group().split(".")) if match else None


def major_status(major: int, requires: str, tested: str) -> str:
    low, high = parse_version(requires), parse_version(tested)
    if low is None or high is None:
        return UNKNOWN
    return OK if low[0] <= major <= high[0] else NG


def site_supported(wp_version: str, requires: str, tested: str) -> bool | None:
    """サイトの版が対応範囲にあるか。判定できなければ None。"""
    version, low, high = parse_version(wp_version), parse_version(requires), parse_version(tested)
    if version is None or low is None or high is None:
        return None
    # tested は 7.0.6 のようにパッチまで持つが、同じマイナー版なら動作確認済みとみなす
    return version >= low and version[:2] <= high[:2]


def fetch_site(runner: Runner, site: Site, main_dir: Path = MAIN_DIR) -> SiteResult:
    """サイトを起動せず、html ボリュームと DB を共有する WP-CLI のコンテナで取得する。"""

    def wp(*args: str):
        return compose(
            runner, "run", "--rm", "-T", "--quiet-pull", site.cli_service, "wp", *args,
            cwd=main_dir, check=False, capture=True, mutate=False,
        )

    core = wp("core", "version")
    if core.returncode != 0:
        detail = (core.stderr or core.stdout or "").strip()
        hint = NOT_INSTALLED_HINT if "not seem to be a WordPress installation" in detail else detail
        return SiteResult(None, (), hint or f"wp core version が失敗しました（exit {core.returncode}）")
    listed = wp("plugin", "list", "--format=json", "--fields=name,title,version,status")
    try:
        if listed.returncode != 0:
            raise ValueError((listed.stderr or listed.stdout or "").strip())
        rows = json.loads(listed.stdout)
    except ValueError as error:
        return SiteResult(None, (), f"wp plugin list が失敗しました: {error}")
    plugins = tuple(
        InstalledPlugin(slug=row["name"], title=html.unescape(row.get("title") or row["name"]),
                        version=row.get("version") or "", status=row["status"])
        for row in rows
        if row.get("status") in LISTED_STATUSES
    )
    return SiteResult(core.stdout.strip(), plugins)


def fetch_org(slug: str, timeout: float = API_TIMEOUT_SECONDS) -> OrgInfo | None:
    """wordpress.org から取得する。届かなければ None（前回の値を残すため、未登録とは区別する）。"""
    query = urllib.parse.urlencode({
        "action": "plugin_information",
        "request[slug]": slug,
        "request[fields][sections]": "0",
    })
    try:
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        return OrgInfo(found=False) if error.code == 404 else None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    if not isinstance(data, dict) or "error" in data:
        return OrgInfo(found=False)
    return OrgInfo(
        found=True,
        name=html.unescape(data.get("name") or slug),
        requires=str(data.get("requires") or ""),
        tested=str(data.get("tested") or ""),
    )


@contextmanager
def refresh_lock(lock_dir: Path | None = None) -> Iterator[None]:
    """gunicorn の worker をまたいで、再取得を 1 つに限る。"""
    lock_dir = lock_dir or LOCK_DIR
    lock_dir.mkdir(parents=True, exist_ok=True)
    with open(lock_dir / "plugins.lock", "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Busy() from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


OrgFetcher = Callable[[str], OrgInfo | None]
