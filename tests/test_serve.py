import importlib
import signal

import pytest

from wp_main import power, processes, session
from wp_main.config import SITES

WP1, WP2 = SITES
serve_command = importlib.import_module("wp_main.cli.management.commands.serve")


@pytest.fixture
def up_env(monkeypatch):
    """serve up の前段だけを動かし、監督の本体は呼び出しの記録にする。"""
    calls: list = []
    monkeypatch.setattr(processes, "port_in_use", lambda port: False)
    monkeypatch.setattr(session, "status", lambda path=None: None)
    monkeypatch.setattr(session, "rotate_logs", lambda log_dir=None: calls.append("rotate"))

    def supervise_session(runner, sites, root, port, *, prepare, terminal):
        calls.append(("session", [site.id for site in sites], terminal))
        return 0

    monkeypatch.setattr(session, "supervise_session", supervise_session)
    return calls


def test_serve_without_subcommand_points_to_up(up_env, manage):
    result = manage("serve", "--site=wp1")
    assert result.exit_code == 1
    assert "uv run manage.py serve up --site=wp1" in result.stderr
    assert up_env == []


def test_up_runs_session_in_foreground(up_env, manage):
    assert manage("serve", "up", "--site=wp2,wp1").exit_code == 0
    assert up_env == ["rotate", ("session", ["wp2", "wp1"], True)]


def test_up_unknown_site_starts_nothing(up_env, manage):
    result = manage("serve", "up", "--site=wp3")
    assert result.exit_code == 1 and "wp1, wp2, all" in result.stderr
    assert up_env == []


def test_up_busy_port_starts_nothing(up_env, monkeypatch, manage):
    monkeypatch.setattr(processes, "port_in_use", lambda port: True)
    result = manage("serve", "up", "--site=wp1")
    assert result.exit_code == 1 and "DASHBOARD_PORT" in result.stderr
    assert up_env == []


def test_up_replaces_running_session(up_env, monkeypatch, manage):
    requested = []
    monkeypatch.setattr(session, "status", lambda path=None: session.Info(4321, session.READY))
    monkeypatch.setattr(session, "request_end", lambda signum, *a, **k: requested.append(signum))
    result = manage("serve", "up", "--site=wp2")
    assert result.exit_code == 0 and "PID 4321" in result.stdout
    assert requested == [signal.SIGUSR1]
    assert up_env[-1] == ("session", ["wp2"], True)


class FakeChild:
    pid = 777

    def __init__(self, code):
        self.code = code
        self.returncode = code

    def poll(self):
        return self.code


@pytest.fixture
def detached(up_env, monkeypatch):
    spawned = []

    def spawn(code):
        def popen(command, **kwargs):
            spawned.append((command, kwargs))
            return FakeChild(code)

        monkeypatch.setattr(serve_command.subprocess, "Popen", popen)

    monkeypatch.setattr(serve_command, "DETACH_POLL_SECONDS", 0)
    return spawned, spawn


def test_detach_returns_when_ready(detached, monkeypatch, manage):
    spawned, spawn = detached
    spawn(None)
    monkeypatch.setattr(session, "status", lambda path=None: None)
    statuses = iter([None, session.Info(777, session.READY, ("wp2",))])
    result_holder = {}

    def status(path=None):
        # 前のセッションの確認（1 回目）の後は、子の起動を待つ間の状態を返す
        if "checked" not in result_holder:
            result_holder["checked"] = True
            return None
        return next(statuses)

    monkeypatch.setattr(session, "status", status)
    result = manage("serve", "up", "--detach", "--site=wp1,wp2")
    assert result.exit_code == 0
    assert "開発セッションを始めました" in result.stdout and "wp2 は起動できませんでした" in result.stderr
    [(command, kwargs)] = spawned
    assert command[2:5] == ["serve", "supervise", "--root"] and command[-2:] == ["--site", "wp1,wp2"]
    assert kwargs["start_new_session"] is True


def test_detach_failure_shows_log_tail(detached, isolated_session, manage):
    spawned, spawn = detached
    spawn(1)
    log_dir = isolated_session / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "serve.log").write_text("共有インフラを起動できません: Cannot connect to the Docker daemon\n")
    result = manage("serve", "up", "--detach")
    assert result.exit_code == 1
    assert "Cannot connect to the Docker daemon" in result.stderr and "serve logs" in result.stderr


@pytest.fixture
def down_env(monkeypatch):
    calls: list = []
    state = {"session": None, "sites": [], "infra": False, "stale": False}
    monkeypatch.setattr(session, "request_end", lambda signum, *a, **k: calls.append(("signal", signum)) or state["session"])
    monkeypatch.setattr(power, "running_sites", lambda runner: state["sites"])
    monkeypatch.setattr(session, "operate", lambda runner, site, root, action, echo: calls.append((action, site.id)))
    monkeypatch.setattr(power, "infra_exists", lambda runner: state["infra"])
    monkeypatch.setattr(power, "stop_infra", lambda runner: calls.append(("infra-down",)))
    monkeypatch.setattr(session, "clear_stale", lambda path=None: state["stale"])
    return calls, state


def test_down_ends_running_session(down_env, manage):
    calls, state = down_env
    state["session"] = session.Info(4321, session.READY)
    result = manage("serve", "down")
    assert result.exit_code == 0 and "PID 4321" in result.stdout
    assert calls == [("signal", signal.SIGTERM)]


def test_down_cleans_up_leftovers(down_env, manage):
    calls, state = down_env
    state.update(sites=[WP1], infra=True, stale=True)
    result = manage("serve", "down")
    assert result.exit_code == 0
    assert calls == [("signal", signal.SIGTERM), ("stop", "wp1"), ("infra-down",)]
    assert "ありません" not in result.stdout


def test_down_with_nothing_running(down_env, manage):
    calls, _ = down_env
    result = manage("serve", "down")
    assert result.exit_code == 0 and "開発セッションはありません" in result.stdout
    assert calls == [("signal", signal.SIGTERM)]


def test_logs_unknown_name(manage, monkeypatch):
    result = manage("serve", "logs", "wp3")
    assert result.exit_code == 1
    assert "dashboard" in result.stderr and "wp1" in result.stderr
