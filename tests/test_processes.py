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


def test_old_devenv_serve_points_to_serve_up(monkeypatch, manage):
    monkeypatch.setattr(processes, "supervise", lambda *args, **kwargs: pytest.fail("起動してはならない"))
    result = manage("devenv", "serve")
    assert result.exit_code == 1
    assert "uv run manage.py serve up" in result.stderr


def test_output_goes_to_log_files(tmp_path):
    lines: list[str] = []
    stop = threading.Event()
    printer = "import time; print('hello', flush=True); time.sleep(60)"
    threading.Timer(1.0, stop.set).start()
    assert supervise([python("dashboard", printer)], stop=stop, echo=lines.append, log_dir=tmp_path) == 0
    assert (tmp_path / "dashboard.log").read_text() == "hello\n"
    assert lines == ["dashboard | hello"]


def test_on_ready_is_called_once():
    ready_calls: list[bool] = []
    stop = threading.Event()
    threading.Timer(1.0, stop.set).start()
    code = supervise(
        [python("dashboard", "import time; time.sleep(60)")], stop=stop, echo=lambda line: None,
        ready=lambda: True, on_ready=lambda: ready_calls.append(True),
    )
    assert code == 0 and ready_calls == [True]


def test_not_ready_in_time_fails(capsys):
    code = supervise(
        [python("dashboard", "import time; time.sleep(60)")], echo=lambda line: None,
        ready=lambda: False, on_ready=lambda: pytest.fail("呼ばれてはならない"), ready_timeout=0.5,
    )
    assert code == 1
    assert "応答しませんでした" in capsys.readouterr().err
