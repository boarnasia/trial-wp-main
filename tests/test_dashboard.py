import pytest
from django.test import Client

from wp_main.dashboard.data import github_url, load_db, load_sites, wordpress_version

WP1_ENV = """\
WP_IMAGE=wordpress:7.1-apache
WP_DEBUG_PORT=8081
WP_HOME=https://local.wp1.yamashita109.com
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=secret-wp1
"""
WP2_ENV = WP1_ENV.replace("7.1", "6.7").replace("8081", "8082").replace("wp1", "wp2")


MAIN_ENV = """\
DB_USER=wordpress
DB_PASSWORD=secret-user
DB_ROOT_PASSWORD=secret-root
"""


@pytest.fixture
def sites_dir(tmp_path, monkeypatch):
    for site_id, text in (("wp1", WP1_ENV), ("wp2", WP2_ENV)):
        (tmp_path / f"wp-{site_id}").mkdir()
        (tmp_path / f"wp-{site_id}" / ".env").write_text(text)
    monkeypatch.setenv("WP_MAIN_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def main_dir(tmp_path, monkeypatch):
    """実際の wp-main の .env を読まないよう、一時ディレクトリの .env を読ませる。"""
    path = tmp_path / "wp-main"
    path.mkdir()
    (path / ".env").write_text(MAIN_ENV)
    monkeypatch.setenv("WP_MAIN_DIR", str(path))
    return path


@pytest.fixture(autouse=True)
def docker_state(monkeypatch, tmp_path):
    """実際の Docker に問い合わせないよう、全サイトが起動中として扱う。"""
    from wp_main import power

    from wp_main import versioning

    monkeypatch.setattr(power, "inspect", lambda runner, site: power.SiteState(power.RUNNING))
    monkeypatch.setattr(power, "inspect_mysql", lambda runner: power.SiteState(power.RUNNING))
    monkeypatch.setattr(power, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(versioning, "installed_version", lambda root: 6)
    monkeypatch.setattr(versioning, "latest", lambda: 6)


@pytest.fixture
def client(sites_dir, db):
    return Client()


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
    (sites_dir / "wp-wp2" / ".env").unlink()
    wp1, wp2 = load_sites()
    assert wp1.env_found
    assert not wp2.env_found and wp2.env_path == "../wp-wp2/.env"


def test_missing_password(sites_dir):
    (sites_dir / "wp-wp1" / ".env").write_text(WP1_ENV.replace("WP_ADMIN_PASSWORD=secret-wp1\n", ""))
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
    (sites_dir / "wp-wp2" / ".env").unlink()
    response = client.get("/")
    assert response.status_code == 200
    assert "../wp-wp2/.env が見つかりません" in response.text
    assert "WordPress 7.1" in response.text


def test_index_disables_buttons_without_password(client, sites_dir):
    (sites_dir / "wp-wp1" / ".env").write_text(WP1_ENV.replace("WP_ADMIN_PASSWORD=secret-wp1\n", ""))
    html = client.get("/").text
    assert 'data-secret-toggle="site-wp1"' not in html
    assert "wp1 のパスワードは未設定" in html
    assert 'data-secret-toggle="site-wp2"' in html


def test_password_api_reads_env_each_time(client, sites_dir):
    first = client.get("/api/sites/wp1/password")
    assert first.status_code == 200
    assert first.json() == {"password": "secret-wp1"}
    assert first.headers["Cache-Control"] == "no-store"

    (sites_dir / "wp-wp1" / ".env").write_text(WP1_ENV.replace("secret-wp1", "changed"))
    assert client.get("/api/sites/wp1/password").json() == {"password": "changed"}


def test_password_api_unknown_site(client):
    response = client.get("/api/sites/wp9/password")
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_index_supports_head(client):
    assert client.head("/").status_code == 200


def test_login_link_opens_new_tab(client):
    html = client.get("/").text
    assert 'href="https://local.wp1.yamashita109.com/wp-login.php" target="_blank" rel="noopener noreferrer"' in html


def test_url_label_strips_scheme_and_slash(sites_dir):
    wp1, _ = load_sites()
    assert wp1.url_label == "local.wp1.yamashita109.com"


def test_static_files_are_served(client):
    for name in ("dist/dashboard.css", "dist/dashboard.js"):
        response = client.get(f"/static/{name}")
        assert response.status_code == 200
        assert b"".join(response.streaming_content if response.streaming else [response.content])


def test_index_rejects_post(client):
    assert client.post("/").status_code == 405


def test_favicon(client):
    assert 'rel="icon" href="/static/favicon.svg"' in client.get("/").content.decode()
    response = client.get("/favicon.ico")
    assert response.status_code == 301 and response.headers["Location"] == "/static/favicon.svg"
    assert client.get("/static/favicon.svg").status_code == 200


def add_operation(minute, **values):
    from datetime import datetime, timezone

    from wp_main.dashboard.models import Operation

    finished = datetime(2026, 9, 27, 1, minute, tzinfo=timezone.utc)
    fields = {"command": "migrate", "options": {}, "started_at": finished, "finished_at": finished,
              "exit_code": 0, "succeeded": True, "summary": "3 → 4"} | values
    return Operation.objects.create(**fields)


def test_history_newest_first_and_marks_failure(client):
    add_operation(0)
    add_operation(5, command="check-health", exit_code=1, succeeded=False, summary="OK 26 / WARN 0 / FAIL 1 / SKIP 0")
    html = client.get("/").content.decode()
    assert html.index("check-health") < html.index("3 → 4")
    assert "history-row failed" in html and "失敗" in html
    assert "2026-09-27 10:05:00" in html


def test_history_limited_to_recent(client):
    for minute in range(25):
        add_operation(minute, summary=f"op-{minute:02d}")
    html = client.get("/").content.decode()
    assert "op-24" in html and "op-05" in html and "op-04" not in html


def test_history_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "操作履歴はまだありません" in response.content.decode()
    assert "WordPress 7.1" in response.content.decode()


def test_db_connection_defaults(main_dir):
    db = load_db()
    assert db.address == "127.0.0.1:3306"
    assert (db.root.user, db.user.user) == ("root", "wordpress")
    assert db.root.has_password and db.user.has_password and db.placeholder_keys == ()


def test_db_connection_custom_port_and_missing_password(main_dir):
    (main_dir / ".env").write_text("MYSQL_PORT=13306\nDB_USER=wp\nDB_ROOT_PASSWORD=change-me\n")
    db = load_db()
    assert db.address == "127.0.0.1:13306" and db.user.user == "wp"
    assert not db.user.has_password
    assert db.placeholder_keys == ("DB_ROOT_PASSWORD",)


def test_index_shows_db_connection_without_passwords(client):
    html = client.get("/").text
    assert "127.0.0.1:3306" in html and "wordpress" in html
    assert 'data-secret-toggle="db-root"' in html and 'data-secret-toggle="db-user"' in html
    assert "secret-root" not in html and "secret-user" not in html


def test_index_warns_placeholder_and_disables_missing(client, main_dir):
    (main_dir / ".env").write_text("DB_ROOT_PASSWORD=change-me\n")
    html = client.get("/").text
    assert "DB_ROOT_PASSWORD" in html and "change-me" in html
    assert 'data-secret-toggle="db-user"' not in html and "共用ユーザーのパスワードは未設定" in html


def test_db_password_api_reads_env_each_time(client, main_dir):
    response = client.get("/api/db/root/password")
    assert response.json() == {"password": "secret-root"}
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/api/db/user/password").json() == {"password": "secret-user"}
    (main_dir / ".env").write_text(MAIN_ENV.replace("secret-root", "rotated"))
    assert client.get("/api/db/root/password").json() == {"password": "rotated"}


@pytest.mark.parametrize("account", ["admin", "user"])
def test_db_password_api_not_found(client, main_dir, account):
    (main_dir / ".env").write_text("DB_ROOT_PASSWORD=secret-root\n")
    response = client.get(f"/api/db/{account}/password")
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(("state", "label"), [
    ("running", "起動中"), ("starting", "処理中"), ("stopped", "停止中"), ("unknown", "取得不可"),
])
def test_mysql_state(client, monkeypatch, state, label):
    from wp_main import power

    monkeypatch.setattr(power, "inspect_mysql", lambda runner: power.SiteState(state))
    html = client.get("/").text
    assert f'class="state {state} ' in html and f">{label}<" in html


def test_github_links(client):
    assert github_url("git@github.com:boarnasia/trial-wp-wp1.git") == "https://github.com/boarnasia/trial-wp-wp1"
    assert github_url("https://example.com/repo.git") is None
    html = client.get("/").text
    assert 'href="https://github.com/boarnasia/trial-wp-wp2" target="_blank" rel="noopener noreferrer"' in html
    assert ">WP ログイン</a>" in html


def test_env_version(client, monkeypatch):
    from wp_main import versioning

    assert "環境 v6" in client.get("/").text
    monkeypatch.setattr(versioning, "installed_version", lambda root: 5)
    html = client.get("/").text
    assert "環境 v5" in html and "devenv migrate" in html


def test_site_filter_markup(client):
    html = client.get("/").text
    assert 'id="site-filter"' in html
    assert 'data-site-id="wp1"' in html and 'data-site-id="wp2"' in html and "data-site-empty" in html


def post_shutdown(client):
    client.get("/")
    token = client.cookies["csrftoken"].value
    return client.post("/session/shutdown", secure=True, headers={
        "X-CSRFToken": token, "Origin": "https://local.wp-main.yamashita109.com",
    })


@pytest.fixture
def spawned(monkeypatch):
    from wp_main import session

    roots = []
    monkeypatch.setattr(session, "spawn_down", roots.append)
    return roots


def test_shutdown_spawns_serve_down(sites_dir, db, spawned):
    client = Client(enforce_csrf_checks=True)
    assert 'id="shutdown-open"' in client.get("/").text
    response = post_shutdown(client)
    assert response.status_code == 202
    assert spawned == [sites_dir]


def test_shutdown_requires_csrf(sites_dir, db, spawned):
    response = Client(enforce_csrf_checks=True).post("/session/shutdown", secure=True)
    assert response.status_code == 403 and spawned == []


def test_shutdown_rejects_get(client, spawned):
    assert client.get("/session/shutdown").status_code == 405 and spawned == []


def test_shutdown_hidden_and_forbidden_on_lan(sites_dir, db, main_dir, spawned):
    (main_dir / ".env").write_text(MAIN_ENV + "PROXY_BIND_ADDRESS=0.0.0.0\n")
    client = Client(enforce_csrf_checks=True)
    html = client.get("/").text
    assert 'id="shutdown-open"' not in html and 'id="shutdown-dialog"' not in html
    assert post_shutdown(client).status_code == 403 and spawned == []
