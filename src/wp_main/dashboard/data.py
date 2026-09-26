import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..config import SITES, Site
from ..sites import parse_env

REQUIRED_KEYS = ("WP_HOME", "WP_IMAGE", "WP_DEBUG_PORT", "WP_ADMIN_USER", "WP_ADMIN_PASSWORD")
DEFAULT_SITES_DIR = "/sites"


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


def sites_dir() -> Path:
    return Path(os.environ.get("DASHBOARD_SITES_DIR", DEFAULT_SITES_DIR))


def read_site_env(site: Site, base: Path) -> dict[str, str] | None:
    # 表示のたびに読み直し、.env の書き換えを再起動なしで反映する
    try:
        return parse_env((base / site.id / ".env").read_text())
    except FileNotFoundError:
        return None


def wordpress_version(image: str) -> str:
    tag = image.rpartition(":")[2] if ":" in image else "latest"
    match = re.match(r"\d+(?:\.\d+)*", tag)
    return f"WordPress {match.group()}" if match else tag


def build_view(site: Site, env: dict[str, str] | None) -> SiteView:
    env_path = f"../{site.dir_name}/.env"
    if env is None:
        return SiteView(id=site.id, env_path=env_path, env_found=False)
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
    )


def load_sites(base: Path | None = None) -> list[SiteView]:
    base = base or sites_dir()
    return [build_view(site, read_site_env(site, base)) for site in SITES]


def find_password(site_id: str, base: Path | None = None) -> str | None:
    site = next((site for site in SITES if site.id == site_id), None)
    if site is None:
        return None
    env = read_site_env(site, base or sites_dir())
    return (env or {}).get("WP_ADMIN_PASSWORD") or None
