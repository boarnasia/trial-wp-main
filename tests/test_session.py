import os
import signal
import subprocess
import sys

import pytest

from wp_main import power, processes, session
from wp_main.config import SITES
from wp_main.runner import DevEnvError

WP1, WP2 = SITES


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
    monkeypatch.setattr(power, "stop_infra", lambda runner: calls.append(("infra-down", "")))
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


def test_end_stops_every_running_site_then_infra(docker, tmp_path, recorded_operations):
    calls, running, _ = docker
    running.update({"wp1", "wp2"})
    session.end(object(), tmp_path, echo=lambda line: None)
    assert calls == [("stop", "wp1"), ("stop", "wp2"), ("infra-down", "")] and running == set()
    assert {entry["command"] for entry in recorded_operations} == {"site-stop"}


def test_handover_keeps_infra(docker, tmp_path):
    calls, running, _ = docker
    running.add("wp1")
    session.end(object(), tmp_path, echo=lambda line: None, infra=False)
    assert calls == [("stop", "wp1")]


def test_begin_returns_failed_sites(docker, tmp_path):
    _, _, failing = docker
    failing.add("wp2")
    assert session.begin(object(), [WP1, WP2], tmp_path, echo=lambda line: None) == ["wp2"]


def test_hold_records_session_and_removes_it(tmp_path):
    path = tmp_path / "serve.pid"
    assert session.status(path) is None
    with session.hold(path) as holder:
        assert session.status(path) == session.Info(os.getpid(), session.STARTING)
        holder.write(session.READY, ["wp2"])
        assert session.status(path) == session.Info(os.getpid(), session.READY, ("wp2",))
        with pytest.raises(session.Running), session.hold(path):
            pass
    assert session.status(path) is None and not path.exists()


def test_dead_holder_leaves_stale_file(tmp_path):
    path = tmp_path / "serve.pid"
    holder = subprocess.Popen([sys.executable, "-c", (
        "import fcntl, sys, time\n"
        f"handle = open({str(path)!r}, 'a+')\n"
        "fcntl.flock(handle, fcntl.LOCK_EX)\n"
        "handle.write('{\"pid\": 1, \"state\": \"ready\"}'); handle.flush()\n"
        "print('locked', flush=True)\n"
        "time.sleep(60)\n"
    )], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        assert session.is_running(path)
        assert not session.clear_stale(path)
    finally:
        holder.kill()
        holder.wait()
    assert not session.is_running(path)
    assert session.clear_stale(path) and not path.exists()
    with session.hold(path):
        assert session.status(path).pid == os.getpid()


def test_rotate_logs_keeps_one_generation(tmp_path):
    (tmp_path / "dashboard.log").write_text("first\n")
    session.rotate_logs(tmp_path)
    (tmp_path / "dashboard.log").write_text("second\n")
    session.rotate_logs(tmp_path)
    assert (tmp_path / "dashboard.log.1").read_text() == "second\n"
    assert not (tmp_path / "dashboard.log").exists()


@pytest.fixture
def supervised(docker, monkeypatch, tmp_path):
    """processes.supervise の代わりに behave を呼び、supervise_session を動かす。"""
    calls, running, failing = docker
    state = {"behave": lambda kwargs: 0}

    def fake_supervise(procs, **kwargs):
        calls.append(("supervise", ",".join(p.name for p in procs)))
        return state["behave"](kwargs)

    monkeypatch.setattr(processes, "supervise", fake_supervise)

    def run(sites, prepare=lambda: None):
        return session.supervise_session(
            object(), sites, tmp_path, 8123, prepare=prepare, terminal=False,
            session_path=tmp_path / "serve.pid", log_dir=tmp_path / "logs",
        )

    return calls, state, run


def test_session_starts_and_ends_everything(supervised, tmp_path):
    calls, state, run = supervised

    def behave(kwargs):
        kwargs["on_ready"]()
        assert session.status(tmp_path / "serve.pid").state == session.READY
        return 0

    state["behave"] = behave
    assert run([WP1]) == 0
    assert calls == [("infra", ""), ("start", "wp1"), ("supervise", "dashboard"), ("stop", "wp1"), ("infra-down", "")]
    assert not (tmp_path / "serve.pid").exists()


@pytest.mark.parametrize("code", [0, 1])
def test_session_end_runs_whatever_the_exit(supervised, code):
    calls, state, run = supervised
    state["behave"] = lambda kwargs: code
    assert run([WP1]) == code
    assert calls[-2:] == [("stop", "wp1"), ("infra-down", "")]


def test_sigusr1_hands_over_without_stopping_infra(supervised):
    calls, state, run = supervised

    def behave(kwargs):
        os.kill(os.getpid(), signal.SIGUSR1)
        assert kwargs["stop"].wait(5)
        return 0

    state["behave"] = behave
    assert run([WP1]) == 0
    assert ("stop", "wp1") in calls and ("infra-down", "") not in calls


def test_sigterm_stops_infra(supervised):
    calls, state, run = supervised

    def behave(kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        assert kwargs["stop"].wait(5)
        return 0

    state["behave"] = behave
    assert run([]) == 0
    assert calls[-1] == ("infra-down", "")


def test_infra_failure_stops_infra_and_starts_nothing(supervised, monkeypatch, tmp_path):
    calls, _, run = supervised

    def broken(runner):
        raise DevEnvError("Cannot connect to the Docker daemon")

    monkeypatch.setattr(power, "start_infra", broken)
    assert run([WP1]) == 1
    assert calls == [("infra-down", "")]
    assert not (tmp_path / "serve.pid").exists()


def test_db_failure_starts_nothing(supervised):
    calls, _, run = supervised

    def prepare():
        raise RuntimeError("disk full")

    assert run([WP1], prepare=prepare) == 1
    assert calls == []


def test_second_session_is_refused(supervised, tmp_path):
    calls, _, run = supervised
    with session.hold(tmp_path / "serve.pid"), pytest.raises(session.Running):
        run([WP1])
    assert calls == []


def test_foreground_session_also_writes_serve_log(supervised, monkeypatch, tmp_path, capsys):
    _, _, _ = supervised
    session.supervise_session(
        object(), [WP1], tmp_path, 8123, prepare=lambda: None, terminal=True,
        session_path=tmp_path / "serve.pid", log_dir=tmp_path / "logs",
    )
    log = (tmp_path / "logs" / "serve.log").read_text()
    assert "wp1 を起動します" in log and "共有インフラ（プロキシ・MySQL）を停止します" in log
    assert "wp1 を起動します" in capsys.readouterr().out


def lock_holder(path, *, ignore_term: bool) -> subprocess.Popen:
    """別プロセスで開発セッションの記録を持つ。ignore_term なら SIGTERM を無視する。"""
    code = (
        "import fcntl, json, os, signal, time\n"
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_term else "")
        + f"handle = open({str(path)!r}, 'a+')\n"
        "fcntl.flock(handle, fcntl.LOCK_EX)\n"
        "handle.write(json.dumps({'pid': os.getpid(), 'state': 'ready'})); handle.flush()\n"
        "print('locked', flush=True)\n"
        "time.sleep(60)\n"
    )
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    return holder


def test_request_end_signals_and_waits(tmp_path):
    path = tmp_path / "serve.pid"
    holder = lock_holder(path, ignore_term=False)
    try:
        info = session.request_end(signal.SIGTERM, path, timeout=5)
        assert info.pid == holder.pid and not session.is_running(path)
    finally:
        holder.kill()
        holder.wait()


def test_request_end_kills_after_timeout(tmp_path, monkeypatch):
    path = tmp_path / "serve.pid"
    holder = lock_holder(path, ignore_term=True)
    try:
        with pytest.raises(DevEnvError, match="終わりませんでした"):
            session.request_end(signal.SIGTERM, path, timeout=0.5)
        assert session.request_end(signal.SIGTERM, path, timeout=0.5, kill=True).pid == holder.pid
        assert not session.is_running(path)
    finally:
        holder.kill()
        holder.wait()


def test_request_end_without_session(tmp_path):
    assert session.request_end(signal.SIGTERM, tmp_path / "serve.pid") is None


def test_spawn_down_detaches_and_logs(tmp_path, monkeypatch):
    import subprocess

    started = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            started.update(command=command, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    session.spawn_down(tmp_path / "sites", log_dir=tmp_path / "logs")
    assert started["command"][-4:] == ["serve", "down", "--root", str(tmp_path / "sites")]
    assert started["start_new_session"] is True
    assert (tmp_path / "logs" / "serve.log").exists()
