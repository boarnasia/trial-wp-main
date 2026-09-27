import shutil

import yaml

from wp_main.config import MAIN_DIR, SITES, Site
from wp_main.sites import SECRET_PLACEHOLDER, ensure_env, parse_env


def main_compose() -> dict:
    return yaml.safe_load((MAIN_DIR / "docker-compose.yml").read_text())


def site_compose(site: Site) -> dict | None:
    path = MAIN_DIR / "compose" / f"{site.id}.yml"
    return yaml.safe_load(path.read_text()) if path.exists() else None


def missing_definitions(sites) -> list[str]:
    included = {entry["path"] for entry in main_compose()["include"]}
    missing = []
    for site in sites:
        definition = site_compose(site)
        services = (definition or {}).get("services", {})
        if f"compose/{site.id}.yml" not in included:
            missing.append(f"{site.id}: include")
        for service in (site.wordpress_service, site.cli_service):
            if service not in services:
                missing.append(f"{site.id}: {service}")
    return missing


def test_every_site_has_definitions():
    assert missing_definitions(SITES) == []


def test_missing_site_is_reported():
    extra = Site("wp3", "wp-wp3", "git@example.com:wp3.git", "wordpress:6.7-apache", 8083, "local.wp3.test", "wp3")
    assert missing_definitions((*SITES, extra)) == ["wp3: include", "wp3: wp3-wordpress", "wp3: wp3-cli"]


def test_sites_read_their_own_env_and_do_not_restart():
    includes = {entry["path"]: entry for entry in main_compose()["include"]}
    for site in SITES:
        entry = includes[f"compose/{site.id}.yml"]
        assert entry["project_directory"] == f"../{site.dir_name}"
        assert entry["env_file"] == [f"${{{site.id.upper()}_ENV_FILE:-../{site.dir_name}/.env}}"]
        wordpress = site_compose(site)["services"][site.wordpress_service]
        assert "restart" not in wordpress
        assert wordpress["depends_on"]["mysql"]["condition"] == "service_healthy"


def test_shared_mysql_is_loopback_only_and_hidden_from_proxy():
    mysql = main_compose()["services"]["mysql"]
    assert mysql["container_name"] == "wp-mysql"
    assert mysql["ports"] == ["127.0.0.1:${MYSQL_PORT:-3306}:3306"]
    assert mysql["networks"] == ["wp-db"]
    assert "healthcheck" in mysql
    assert main_compose()["volumes"]["mysql_data"]["name"] == "wp-mysql-data"


def test_main_env_example_generates_db_secrets(tmp_path, fake_runner):
    shutil.copy(MAIN_DIR / ".env.example", tmp_path / ".env.example")
    ensure_env(fake_runner(), tmp_path)
    env = parse_env((tmp_path / ".env").read_text())
    assert env["DB_USER"] == "wordpress"
    for key in ("DB_PASSWORD", "DB_ROOT_PASSWORD"):
        assert env[key] and env[key] != SECRET_PLACEHOLDER
