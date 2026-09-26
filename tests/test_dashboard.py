import pytest
from fastapi.testclient import TestClient

from wp_main.dashboard.app import app
from wp_main.dashboard.data import load_sites, wordpress_version

WP1_ENV = """\
WP_IMAGE=wordpress:7.1-apache
WP_DEBUG_PORT=8081
WP_HOME=https://local.wp1.yamashita109.com
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=secret-wp1
"""
WP2_ENV = WP1_ENV.replace("7.1", "6.7").replace("8081", "8082").replace("wp1", "wp2")


@pytest.fixture
def sites_dir(tmp_path, monkeypatch):
    for site_id, text in (("wp1", WP1_ENV), ("wp2", WP2_ENV)):
        (tmp_path / site_id).mkdir()
        (tmp_path / site_id / ".env").write_text(text)
    monkeypatch.setenv("DASHBOARD_SITES_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(sites_dir):
    return TestClient(app)


def test_version_from_image_tag():
    assert wordpress_version("wordpress:7.1-apache") == "WordPress 7.1"
    assert wordpress_version("wordpress:6.7.2-php8.3-apache") == "WordPress 6.7.2"
    assert wordpress_version("wordpress:latest") == "latest"
    assert wordpress_version("wordpress") == "latest"


def test_load_sites(sites_dir):
    wp1, wp2 = load_sites()
    assert (wp1.id, wp2.id) == ("wp1", "wp2")
    assert wp1.url == "https://local.wp1.yamashita109.com/"
    assert wp1.login_url == "https://local.wp1.yamashita109.com/wp-login.php"
    assert wp1.version == "WordPress 7.1"
    assert wp1.debug_port == "127.0.0.1:8081"
    assert wp1.user == "admin" and wp1.has_password and wp1.missing == ()
    assert wp2.debug_port == "127.0.0.1:8082"


def test_missing_env(sites_dir):
    (sites_dir / "wp2" / ".env").unlink()
    wp1, wp2 = load_sites()
    assert wp1.env_found
    assert not wp2.env_found and wp2.env_path == "../wp-wp2/.env"


def test_missing_password(sites_dir):
    (sites_dir / "wp1" / ".env").write_text(WP1_ENV.replace("WP_ADMIN_PASSWORD=secret-wp1\n", ""))
    wp1, _ = load_sites()
    assert not wp1.has_password
    assert wp1.missing == ("WP_ADMIN_PASSWORD",)


def test_index_lists_sites_without_passwords(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "WordPress 7.1" in html and "WordPress 6.7" in html
    assert 'href="https://local.wp1.yamashita109.com/wp-login.php"' in html
    assert "127.0.0.1:8081" in html
    assert "secret-wp1" not in html and "secret-wp2" not in html


def test_index_with_missing_env(client, sites_dir):
    (sites_dir / "wp2" / ".env").unlink()
    response = client.get("/")
    assert response.status_code == 200
    assert "../wp-wp2/.env が見つかりません" in response.text
    assert "WordPress 7.1" in response.text


def test_index_disables_buttons_without_password(client, sites_dir):
    (sites_dir / "wp1" / ".env").write_text(WP1_ENV.replace("WP_ADMIN_PASSWORD=secret-wp1\n", ""))
    html = client.get("/").text
    assert 'data-toggle="wp1"' not in html
    assert "wp1 のパスワードは未設定" in html
    assert 'data-toggle="wp2"' in html


def test_password_api_reads_env_each_time(client, sites_dir):
    first = client.get("/api/sites/wp1/password")
    assert first.status_code == 200
    assert first.json() == {"password": "secret-wp1"}
    assert first.headers["cache-control"] == "no-store"

    (sites_dir / "wp1" / ".env").write_text(WP1_ENV.replace("secret-wp1", "changed"))
    assert client.get("/api/sites/wp1/password").json() == {"password": "changed"}


def test_password_api_unknown_site(client):
    response = client.get("/api/sites/wp9/password")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_index_supports_head(client):
    assert client.head("/").status_code == 200


def test_login_link_opens_new_tab(client):
    html = client.get("/").text
    assert 'href="https://local.wp1.yamashita109.com/wp-login.php" target="_blank" rel="noopener noreferrer"' in html
