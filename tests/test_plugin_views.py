import pytest
from django.test import Client

from wp_main import plugins, versioning
from wp_main.config import SITES
from wp_main.dashboard import plugin_list
from wp_main.dashboard.models import PluginInfo, SiteFetch, SitePlugin

WP1, WP2 = SITES
QM = plugins.InstalledPlugin("query-monitor", "Query Monitor", "3.17.2", "active")
CE = plugins.InstalledPlugin("classic-editor", "Classic Editor", "1.6.7", "inactive")
YOAST = plugins.InstalledPlugin("wordpress-seo", "Yoast SEO", "24.9", "active")
MU = plugins.InstalledPlugin("in-house", "社内プラグイン", "1.2.0", "must-use")
ORG = {
    "query-monitor": plugins.OrgInfo(True, "Query Monitor", "6.2", "7.0.6"),
    "classic-editor": plugins.OrgInfo(True, "Classic Editor", "4.9", "6.9"),
    "wordpress-seo": plugins.OrgInfo(True, "Yoast SEO", "6.8", "7.0"),
}


@pytest.fixture(autouse=True)
def environment(tmp_path, monkeypatch):
    for site in SITES:
        (tmp_path / site.dir_name).mkdir()
        (tmp_path / site.dir_name / ".env").write_text(f"WP_IMAGE={site.image}\n")
    (tmp_path / "wp-main").mkdir()
    (tmp_path / "wp-main" / ".env").write_text("")
    monkeypatch.setenv("WP_MAIN_ROOT", str(tmp_path))
    monkeypatch.setenv("WP_MAIN_DIR", str(tmp_path / "wp-main"))
    monkeypatch.setattr(versioning, "installed_version", lambda root: 6)
    monkeypatch.setattr(versioning, "latest", lambda: 6)
    monkeypatch.setattr(plugins, "LOCK_DIR", tmp_path / "locks")
    from wp_main import power

    monkeypatch.setattr(power, "inspect", lambda runner, site: power.SiteState(power.RUNNING))
    monkeypatch.setattr(power, "inspect_mysql", lambda runner: power.SiteState(power.RUNNING))
    monkeypatch.setattr(power, "LOCK_DIR", tmp_path / "locks")


def fake_sites(results):
    return lambda runner, site: results[site.id]


def do_refresh(results, org=ORG):
    return plugin_list.refresh(object(), fetch_site=fake_sites(results), fetch_org=lambda slug: org.get(slug))


OK_RESULTS = {
    "wp1": plugins.SiteResult("7.1", (QM, MU)),
    "wp2": plugins.SiteResult("6.7.2", (CE, YOAST, MU)),
}


@pytest.mark.django_db
def test_refresh_stores_and_summarizes():
    result = do_refresh(OK_RESULTS)
    assert result.succeeded and result.summary == "wp1 2 件・wp2 3 件・wordpress.org 3/3"
    assert SitePlugin.objects.count() == 5
    assert set(PluginInfo.objects.values_list("slug", flat=True)) == {"query-monitor", "classic-editor", "wordpress-seo"}


@pytest.mark.django_db
def test_failed_site_keeps_previous_plugins():
    do_refresh(OK_RESULTS)
    result = do_refresh({"wp1": plugins.SiteResult("7.1", (QM,)), "wp2": plugins.SiteResult(None, (), "boom")})
    assert not result.succeeded and "wp2 取得失敗" in result.summary
    assert SitePlugin.objects.filter(site_id="wp2").count() == 3
    assert SitePlugin.objects.filter(site_id="wp1").count() == 1
    wp2 = SiteFetch.objects.get(site_id="wp2")
    assert not wp2.succeeded and wp2.error == "boom" and wp2.succeeded_at is not None


@pytest.mark.django_db
def test_unreachable_org_keeps_previous_info():
    do_refresh(OK_RESULTS)
    result = do_refresh(OK_RESULTS, org={})
    assert not result.succeeded and "wordpress.org 0/3" in result.summary
    assert PluginInfo.objects.get(slug="wordpress-seo").requires == "6.8"


@pytest.mark.django_db
def test_table():
    do_refresh(OK_RESULTS)
    table = plugin_list.build_table()
    assert [site.id for site in table.sites] == ["wp1", "wp2"] and table.majors == [6, 7]
    rows = {row.slug: row for row in table.rows}
    assert [row.title for row in table.rows] == ["Classic Editor", "Query Monitor", "Yoast SEO", "社内プラグイン"]
    assert rows["query-monitor"].url == "https://wordpress.org/plugins/query-monitor/"
    assert [status for _, status, _ in rows["classic-editor"].majors] == [plugins.OK, plugins.NG]
    seo = {cell.site: cell for cell in rows["wordpress-seo"].cells}
    assert seo["wp2"].warning == "6.7.2 非対応" and not seo["wp1"].installed
    assert rows["in-house"].url is None and {s for _, s, _ in rows["in-house"].majors} == {plugins.UNKNOWN}


@pytest.fixture
def client(db):
    return Client()


def test_menu_links_to_plugins(client):
    html = client.get("/").text
    assert 'href="/wordpress/plugins"' in html and ">WordPress<" in html
    response = client.get("/wordpress")
    assert response.status_code == 302 and response["Location"] == "/wordpress/plugins"


def test_empty_page(client):
    html = client.get("/wordpress/plugins").text
    assert "まだ取得していません" in html and 'action="/wordpress/plugins/refresh"' in html
    assert 'aria-current="page"' in html and "プラグイン横断リスト" in html


def test_page_shows_table(client):
    do_refresh(OK_RESULTS)
    html = client.get("/wordpress/plugins").text
    assert 'href="https://wordpress.org/plugins/query-monitor/"' in html
    assert "WP 6 対応" in html and "WP 7 対応" in html
    assert "1.6.7（無効）" in html and ">MU<" in html and "6.7.2 非対応" in html
    assert 'data-sites="wp1"' in html and "wordpress.org 上の最新版" in html


def test_page_shows_site_error(client):
    do_refresh({"wp1": plugins.SiteResult("7.1", (QM,)), "wp2": plugins.SiteResult(None, (), plugins.NOT_INSTALLED_HINT)})
    html = client.get("/wordpress/plugins").text
    assert "取得失敗" in html and "一度サイトを起動してから" in html


def test_page_does_not_call_docker(client, monkeypatch):
    monkeypatch.setattr(plugins, "fetch_site", lambda *args, **kwargs: pytest.fail("docker を呼んだ"))
    monkeypatch.setattr(plugins, "fetch_org", lambda *args, **kwargs: pytest.fail("wordpress.org を呼んだ"))
    assert client.get("/wordpress/plugins").status_code == 200


def post_refresh(client):
    client.get("/wordpress/plugins")
    token = client.cookies["csrftoken"].value
    return client.post("/wordpress/plugins/refresh", {"csrfmiddlewaretoken": token}, secure=True,
                       headers={"Origin": "https://local.wp-main.yamashita109.com"})


@pytest.mark.django_db
def test_refresh_view_records_operation(monkeypatch, recorded_operations):
    monkeypatch.setattr(plugin_list, "refresh", lambda runner: plugin_list.RefreshResult(False, "wp2 取得失敗"))
    client = Client(enforce_csrf_checks=True)
    response = post_refresh(client)
    assert response.status_code == 302 and response["Location"] == "/wordpress/plugins"
    [entry] = recorded_operations
    assert (entry["command"], entry["succeeded"], entry["summary"]) == ("plugins-refresh", False, "wp2 取得失敗")
    assert "wp2 取得失敗" in client.get("/wordpress/plugins").text


@pytest.mark.django_db
def test_refresh_requires_csrf(monkeypatch):
    monkeypatch.setattr(plugin_list, "refresh", lambda runner: pytest.fail("実行された"))
    assert Client(enforce_csrf_checks=True).post("/wordpress/plugins/refresh", secure=True).status_code == 403
    assert Client().get("/wordpress/plugins/refresh").status_code == 405


@pytest.mark.django_db
def test_refresh_busy(monkeypatch, recorded_operations):
    monkeypatch.setattr(plugin_list, "refresh", lambda runner: pytest.fail("実行された"))
    client = Client(enforce_csrf_checks=True)
    with plugins.refresh_lock():
        post_refresh(client)
    assert recorded_operations == []
    assert "別の再取得で取得中です" in client.get("/wordpress/plugins").text


@pytest.mark.django_db
def test_refresh_allowed_on_lan(tmp_path, monkeypatch, recorded_operations):
    (tmp_path / "wp-main" / ".env").write_text("PROXY_BIND_ADDRESS=0.0.0.0\n")
    monkeypatch.setattr(plugin_list, "refresh", lambda runner: plugin_list.RefreshResult(True, "ok"))
    assert post_refresh(Client(enforce_csrf_checks=True)).status_code == 302
    assert recorded_operations[0]["succeeded"] is True
