from dataclasses import dataclass
from pathlib import Path

MAIN_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = MAIN_DIR / "templates" / "wp-site"
LOCAL_DIR = MAIN_DIR / ".local"
STATE_FILE = LOCAL_DIR / "dev-env-state.json"
CA_CERT_FILE = LOCAL_DIR / "caddy-root.crt"
DB_FILE = LOCAL_DIR / "db.sqlite3"
LOCK_DIR = LOCAL_DIR / "locks"

NETWORK = "wp-global-net"
CADDY_SERVICE = "caddy"
CADDY_IMAGE = "caddy:2"
CADDY_ROOT_CERT = "/data/caddy/pki/authorities/local/root.crt"
CADDY_VOLUMES = ("wp-caddy-data", "wp-caddy-config")
MYSQL_IMAGE = "mysql:8.0"
WP_CLI_IMAGE = "wordpress:cli"
PROXY_PORTS = (80, 443)
DASHBOARD_DOMAIN = "local.wp-main.yamashita109.com"
DEFAULT_DASHBOARD_PORT = 8000
# ダッシュボードをコンテナで動かしていた頃のリソース。旧環境の後片付けにだけ使う
LEGACY_DASHBOARD_CONTAINER = "wp-dashboard"
LEGACY_DASHBOARD_IMAGE = "wp-main-dashboard"
LEGACY_DASHBOARD_VOLUME = "wp-dashboard-data"


@dataclass(frozen=True)
class Site:
    id: str
    dir_name: str
    remote: str
    image: str
    debug_port: int
    domain: str
    title: str

    @property
    def wordpress_service(self) -> str:
        return f"{self.id}-wordpress"

    @property
    def cli_service(self) -> str:
        return f"{self.id}-cli"

    @property
    def volumes(self) -> tuple[str, ...]:
        return (f"{self.id}-db-data", f"{self.id}-html")


SITES = (
    Site(
        id="wp1",
        dir_name="wp-wp1",
        remote="git@github.com:boarnasia/trial-wp-wp1.git",
        image="wordpress:7.1-apache",
        debug_port=8081,
        domain="local.wp1.yamashita109.com",
        title="wp1 (WordPress 7)",
    ),
    Site(
        id="wp2",
        dir_name="wp-wp2",
        remote="git@github.com:boarnasia/trial-wp-wp2.git",
        image="wordpress:6.7-apache",
        debug_port=8082,
        domain="local.wp2.yamashita109.com",
        title="wp2 (WordPress 6)",
    ),
)


def resolve_root(root: Path | None) -> Path:
    return (root if root is not None else MAIN_DIR.parent).expanduser().resolve()
