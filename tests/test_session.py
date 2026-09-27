import importlib

import pytest

from wp_main import power, processes, session
from wp_main.config import SITES
from wp_main.runner import DevEnvError

WP1, WP2 = SITES
serve_command = importlib.import_module("wp_main.cli.management.commands.serve")


def test_resolve_sites():
    assert session.resolve_sites(None) == []
    assert session.resolve_sites("wp2,wp1,wp2") == [WP2, WP1]
    assert session.resolve_sites("all") == [WP1, WP2]


def test_resolve_unknown_site_lists_choices():
    with pytest.raises(DevEnvError, match="wp3.*wp1, wp2, all"):
        session.resolve_sites("wp1,wp3")


@pytest.fixture
def docker(monkeypatch, tmp_path):
    """power の Docker 操作を記録だけにする。running は起動中として扱うサイトの集合。"""
    calls: list[tuple[str, str]] = []
    running: set[str] = set()
    failing: set[str] = set()

    def start(runner, site, root):
        calls.append(("start", site.id))
        if site.id in failing:
            raise DevEnvError(".env がありません")
        running.add(site.id)

    def stop(runner, site, root=None):
        calls.append(("stop", site.id))
        running.discard(site.id)

    monkeypatch.setattr(power, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(power, "start_infra", lambda runner: calls.append(("infra", "")))
    monkeypatch.setattr(power, "start", start)
    monkeypatch.setattr(power, "stop", stop)
    monkeypatch.setattr(power, "running_sites", lambda runner: [site for site in SITES if site.id in running])
    return calls, running, failing


def test_begin_continues_after_site_failure(docker, tmp_path, recorded_operations):
    calls, running, failing = docker
    failing.add("wp1")
    session.begin(object(), [WP1, WP2], tmp_path, echo=lambda line: None)
    assert calls == [("infra", ""), ("start", "wp1"), ("start", "wp2")]
    assert running == {"wp2"}
    assert [(entry["command"], entry["options"], entry["succeeded"]) for entry in recorded_operations] == [
        ("site-start", {"site": "wp1", "via": "serve"}, False),
        ("site-start", {"site": "wp2", "via": "serve"}, True),
    ]


def test_begin_stops_when_infra_fails(docker, tmp_path, monkeypatch):
    calls, _, _ = docker

    def broken(runner):
        raise DevEnvError("Cannot connect to the Docker daemon")

    monkeypatch.setattr(power, "start_infra", broken)
    with pytest.raises(DevEnvError):
        session.begin(object(), [WP1], tmp_path, echo=lambda line: None)
    assert calls == []


def test_end_stops_every_running_site(docker, tmp_path, recorded_operations):
    calls, running, _ = docker
    running.update({"wp1", "wp2"})
    session.end(object(), tmp_path, echo=lambda line: None)
    assert calls == [("stop", "wp1"), ("stop", "wp2")] and running == set()
    assert {entry["command"] for entry in recorded_operations} == {"site-stop"}


@pytest.fixture
def serve_env(monkeypatch, docker):
    monkeypatch.setattr(processes, "port_in_use", lambda port: False)
    monkeypatch.setattr(serve_command, "call_command", lambda *args, **kwargs: None)
    return docker


@pytest.mark.parametrize("supervised", [0, 1])
def test_serve_stops_sites_whatever_the_exit(serve_env, monkeypatch, manage, supervised):
    calls, running, _ = serve_env
    monkeypatch.setattr(processes, "supervise", lambda procs: supervised)
    result = manage("serve", "--site=wp1")
    assert result.exit_code == supervised
    assert calls == [("infra", ""), ("start", "wp1"), ("stop", "wp1")]
    assert running == set()


def test_serve_without_site_starts_only_infra(serve_env, monkeypatch, manage):
    calls, _, _ = serve_env
    monkeypatch.setattr(processes, "supervise", lambda procs: 0)
    assert manage("serve").exit_code == 0
    assert calls == [("infra", "")]


def test_serve_unknown_site_starts_nothing(serve_env, monkeypatch, manage):
    calls, _, _ = serve_env
    monkeypatch.setattr(processes, "supervise", lambda procs: pytest.fail("起動してはならない"))
    result = manage("serve", "--site=wp3")
    assert result.exit_code == 1 and "wp1, wp2, all" in result.stderr
    assert calls == []


def test_serve_infra_failure_starts_no_processes(serve_env, monkeypatch, manage):
    calls, _, _ = serve_env

    def broken(runner):
        raise DevEnvError("Cannot connect to the Docker daemon")

    monkeypatch.setattr(power, "start_infra", broken)
    monkeypatch.setattr(processes, "supervise", lambda procs: pytest.fail("起動してはならない"))
    result = manage("serve", "--site=wp1")
    assert result.exit_code == 1 and "共有インフラを起動できません" in result.stderr
    assert calls == []


def test_serve_busy_port_starts_nothing(serve_env, monkeypatch, manage):
    calls, _, _ = serve_env
    monkeypatch.setattr(processes, "port_in_use", lambda port: True)
    result = manage("serve", "--site=wp1")
    assert result.exit_code == 1 and "DASHBOARD_PORT" in result.stderr
    assert calls == []
