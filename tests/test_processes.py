import sys
import threading
from pathlib import Path

import pytest

from wp_main import processes
from wp_main.processes import HostProcess, host_processes, supervise


def python(name: str, code: str) -> HostProcess:
    return HostProcess(name, [sys.executable, "-c", code])


def test_dashboard_listens_on_loopback_only(tmp_path: Path):
    [dashboard] = host_processes(8123, tmp_path)
    assert dashboard.name == "dashboard"
    assert dashboard.command[dashboard.command.index("--bind") + 1] == "127.0.0.1:8123"
    assert dashboard.env["WP_MAIN_ROOT"] == str(tmp_path)


def test_stop_signal_ends_all_with_zero():
    lines: list[str] = []
    stop = threading.Event()
    sleeper = "import time; print('ready', flush=True); time.sleep(60)"
    timer = threading.Timer(1.0, stop.set)
    timer.start()
    code = supervise([python("web", sleeper), python("vite", sleeper)], stop=stop, echo=lines.append)
    assert code == 0
    assert "web  | ready" in lines and "vite | ready" in lines


def test_crash_stops_the_rest(capsys, monkeypatch):
    monkeypatch.setattr(processes, "STOP_TIMEOUT_SECONDS", 5)
    sleeper = "import time; time.sleep(60)"
    code = supervise([python("dashboard", "raise SystemExit(3)"), python("other", sleeper)], echo=lambda line: None)
    assert code == 1
    assert "dashboard が終了しました (exit 3)" in capsys.readouterr().err


def test_port_in_use():
    import socket

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert processes.port_in_use(port)
    assert not processes.port_in_use(port)


def test_old_devenv_serve_points_to_serve(monkeypatch, manage):
    monkeypatch.setattr(processes, "supervise", lambda *args, **kwargs: pytest.fail("起動してはならない"))
    result = manage("devenv", "serve")
    assert result.exit_code == 1
    assert "uv run manage.py serve" in result.stderr


def test_serve_prepares_db_then_supervises(monkeypatch, manage):
    from wp_main import session

    calls = []
    monkeypatch.setattr(processes, "port_in_use", lambda port: False)
    monkeypatch.setattr("wp_main.cli.management.commands.serve.call_command", lambda *a, **k: calls.append("migrate"))
    monkeypatch.setattr(session, "begin", lambda runner, sites, root: calls.append("begin"))
    monkeypatch.setattr(session, "end", lambda runner, root: calls.append("end"))
    monkeypatch.setattr(processes, "supervise", lambda procs, **kwargs: calls.append([p.name for p in procs]) or 0)
    result = manage("serve")
    assert result.exit_code == 0
    assert calls == ["migrate", "begin", ["dashboard"], "end"]
