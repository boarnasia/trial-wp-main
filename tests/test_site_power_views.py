import pytest
from django.test import Client

from wp_main.dashboard import power, views
from wp_main.dashboard.models import Operation
from wp_main.runner import DevEnvError


@pytest.fixture
def calls(monkeypatch, tmp_path):
    """Docker を操作せず、呼ばれた操作を記録する。"""
    done: list[tuple[str, str]] = []
    monkeypatch.setattr(power, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(power, "inspect", lambda runner, site, root: power.SiteState(power.RUNNING, root))
    monkeypatch.setattr(views, "proxy_is_public", lambda: False)
    monkeypatch.setattr(views, "ACTIONS", {
        "start": (lambda runner, site, root: done.append(("start", site.id)), "起動"),
        "stop": (lambda runner, site, root: done.append(("stop", site.id)), "停止"),
    })
    return done


def post(client: Client, url: str):
    client.get("/")  # CSRF Cookie を受け取る
    token = client.cookies["csrftoken"].value
    return client.post(url, {"csrfmiddlewaretoken": token}, secure=True,
                       headers={"Origin": "https://local.wp-main.yamashita109.com"})


@pytest.mark.django_db
def test_csrf_required(calls):
    client = Client(enforce_csrf_checks=True)
    response = client.post("/sites/wp1/stop", secure=True)
    assert response.status_code == 403
    assert calls == []


@pytest.mark.django_db
def test_get_is_not_allowed(calls):
    assert Client().get("/sites/wp1/stop").status_code == 405
    assert calls == []


@pytest.mark.django_db
def test_public_proxy_forbids(calls, monkeypatch):
    monkeypatch.setattr(views, "proxy_is_public", lambda: True)
    response = post(Client(enforce_csrf_checks=True), "/sites/wp1/stop")
    assert response.status_code == 403
    assert calls == []
    page = Client().get("/").content.decode()
    assert "LAN に公開している" in page and "disabled" in page


@pytest.mark.django_db
def test_stop_records_operation(calls, recorded_operations):
    client = Client(enforce_csrf_checks=True)
    response = post(client, "/sites/wp1/stop")
    assert response.status_code == 302 and response["Location"] == "/"
    assert calls == [("stop", "wp1")]
    [entry] = recorded_operations
    assert (entry["command"], entry["options"], entry["succeeded"]) == ("site-stop", {"site": "wp1"}, True)
    assert "wp1 を停止しました" in client.get("/").content.decode()


@pytest.mark.django_db
def test_failure_is_shown_and_recorded(calls, monkeypatch, recorded_operations):
    def broken(runner, site, root):
        raise DevEnvError(".env がありません")

    monkeypatch.setitem(views.ACTIONS, "start", (broken, "起動"))
    client = Client(enforce_csrf_checks=True)
    post(client, "/sites/wp1/start")
    [entry] = recorded_operations
    assert entry["command"] == "site-start" and entry["succeeded"] is False
    assert "wp1 の起動に失敗しました: .env がありません" in client.get("/").content.decode()


@pytest.mark.django_db
def test_busy_site_is_rejected(calls, recorded_operations):
    from wp_main.config import SITES

    client = Client(enforce_csrf_checks=True)
    client.get("/")
    with power.site_lock(SITES[0]):
        page = client.get("/").content.decode()
        assert "処理中" in page
        post(client, "/sites/wp1/stop")
    assert calls == [] and recorded_operations == []
    assert "別の操作を実行中です" in client.get("/").content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("state", "label", "button"), [
    (power.RUNNING, "起動中", "停止"), (power.STOPPED, "停止中", "起動"), (power.PARTIAL, "一部停止", "停止"),
])
def test_buttons_follow_state(calls, monkeypatch, state, label, button):
    monkeypatch.setattr(power, "inspect", lambda runner, site, root: power.SiteState(state, root))
    page = Client().get("/").content.decode()
    assert f">{label}<" in page and f">{button}</button>" in page


@pytest.mark.django_db
def test_docker_down_still_renders(calls, monkeypatch):
    monkeypatch.setattr(power, "inspect",
                        lambda runner, site, root: power.SiteState(power.UNKNOWN, root, "Cannot connect"))
    response = Client().get("/")
    assert response.status_code == 200
    page = response.content.decode()
    assert ">取得不可<" in page and "disabled>" in page
