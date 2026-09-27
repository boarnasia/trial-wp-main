import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..config import MAIN_DIR, SITES, Site, resolve_root
from ..sites import SECRET_PLACEHOLDER, parse_env, read_env

REQUIRED_KEYS = ("WP_HOME", "WP_IMAGE", "WP_DEBUG_PORT", "WP_ADMIN_USER", "WP_ADMIN_PASSWORD")
GITHUB_REMOTE = re.compile(r"^git@github\.com:(?P<path>[^/]+/[^/]+?)(?:\.git)?$")
DB_HOST = "127.0.0.1"
# docker-compose.yml の既定値と同じ値にする
DEFAULT_DB_PORT = "3306"
DEFAULT_DB_USER = "wordpress"
DB_ACCOUNTS = {"root": "DB_ROOT_PASSWORD", "user": "DB_PASSWORD"}


@dataclass(frozen=True)
class SiteView:
    id: str
    env_path: str
    env_found: bool
    missing: tuple[str, ...] = ()
    url: str | None = None
    login_url: str | None = None
    version: str | None = None
    debug_port: str | None = None
    user: str | None = None
    has_password: bool = False
    github_url: str | None = None

    @property
    def url_label(self) -> str | None:
        return self.url.removeprefix("https://").strip("/") if self.url else None


@dataclass(frozen=True)
class DbAccount:
    key: str
    user: str
    has_password: bool
    is_placeholder: bool


@dataclass(frozen=True)
class DbConnection:
    host: str
    port: str
    root: DbAccount
    user: DbAccount

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def placeholder_keys(self) -> tuple[str, ...]:
        return tuple(DB_ACCOUNTS[account.key] for account in (self.root, self.user) if account.is_placeholder)


def main_dir() -> Path:
    # e2e テストが一時ディレクトリの .env を読ませるために差し替える
    value = os.environ.get("WP_MAIN_DIR")
    return Path(value) if value else MAIN_DIR


def sites_root() -> Path:
    # serve --root の値を、ダッシュボードのプロセスに環境変数で引き継ぐ
    value = os.environ.get("WP_MAIN_ROOT")
    return resolve_root(Path(value) if value else None)


def read_site_env(site: Site, base: Path) -> dict[str, str] | None:
    # 表示のたびに読み直し、.env の書き換えを再起動なしで反映する
    try:
        return parse_env((base / site.dir_name / ".env").read_text())
    except FileNotFoundError:
        return None


def wordpress_version(image: str) -> str:
    tag = image.rpartition(":")[2] if ":" in image else "latest"
    match = re.match(r"\d+(?:\.\d+)*", tag)
    return f"WordPress {match.group()}" if match else tag


def github_url(remote: str) -> str | None:
    match = GITHUB_REMOTE.match(remote)
    return f"https://github.com/{match.group('path')}" if match else None


def build_view(site: Site, env: dict[str, str] | None) -> SiteView:
    env_path = f"../{site.dir_name}/.env"
    if env is None:
        return SiteView(id=site.id, env_path=env_path, env_found=False, github_url=github_url(site.remote))
    value = {key: env.get(key) or None for key in REQUIRED_KEYS}
    home = value["WP_HOME"].rstrip("/") if value["WP_HOME"] else None
    return SiteView(
        id=site.id,
        env_path=env_path,
        env_found=True,
        missing=tuple(key for key in REQUIRED_KEYS if value[key] is None),
        url=f"{home}/" if home else None,
        login_url=f"{home}/wp-login.php" if home else None,
        version=wordpress_version(value["WP_IMAGE"]) if value["WP_IMAGE"] else None,
        debug_port=f"127.0.0.1:{value['WP_DEBUG_PORT']}" if value["WP_DEBUG_PORT"] else None,
        user=value["WP_ADMIN_USER"],
        has_password=value["WP_ADMIN_PASSWORD"] is not None,
        github_url=github_url(site.remote),
    )


def load_sites(base: Path | None = None) -> list[SiteView]:
    base = base or sites_root()
    return [build_view(site, read_site_env(site, base)) for site in SITES]


def find_password(site_id: str, base: Path | None = None) -> str | None:
    site = next((site for site in SITES if site.id == site_id), None)
    if site is None:
        return None
    env = read_site_env(site, base or sites_root())
    return (env or {}).get("WP_ADMIN_PASSWORD") or None


def db_account(key: str, user: str, env: dict[str, str]) -> DbAccount:
    value = env.get(DB_ACCOUNTS[key]) or None
    return DbAccount(key=key, user=user, has_password=value is not None, is_placeholder=value == SECRET_PLACEHOLDER)


def load_db(base: Path | None = None) -> DbConnection:
    # サイトの .env と同じく、書き換えを再起動なしで反映するため毎回読む
    env = read_env(base or main_dir())
    return DbConnection(
        host=DB_HOST,
        port=env.get("MYSQL_PORT") or DEFAULT_DB_PORT,
        root=db_account("root", "root", env),
        user=db_account("user", env.get("DB_USER") or DEFAULT_DB_USER, env),
    )


def find_db_password(account: str, base: Path | None = None) -> str | None:
    if account not in DB_ACCOUNTS:
        return None
    return read_env(base or main_dir()).get(DB_ACCOUNTS[account]) or None
