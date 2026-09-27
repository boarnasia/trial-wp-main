import threading

import pytest

from wp_main import logs, power
from wp_main.runner import DevEnvError


def test_names_map_to_sources(tmp_path):
    found = logs.sources(tmp_path)
    assert found["dashboard"].log_file == tmp_path / "dashboard.log"
    assert found["serve"].log_file == tmp_path / "serve.log"
    assert found["wp1"].service == "wp1-wordpress"
    assert found["mysql"].container == "wp-mysql"


def test_select_unknown_name_lists_choices(fake_runner, tmp_path):
    with pytest.raises(DevEnvError, match="wp3.*dashboard.*caddy.*wp1"):
        logs.select(["wp3"], fake_runner(), tmp_path)


def test_select_defaults_to_what_can_be_read(fake_runner, tmp_path, monkeypatch):
    (tmp_path / "dashboard.log").write_text("x\n")
    monkeypatch.setattr(
        power, "inspect_containers",
        lambda runner, names: {"wp-mysql": {"State": {"Status": "running"}}, "wp1-wordpress": {"State": {"Status": "exited"}}},
    )
    assert [source.name for source in logs.select([], fake_runner(), tmp_path)] == ["dashboard", "mysql"]


def test_compose_logs_command_passes_tail_and_follow(tmp_path):
    source = logs.sources(tmp_path)["wp1"]
    assert logs.compose_logs_command(source, True, 5) == [
        "docker", "compose", "logs", "--no-log-prefix", "-f", "--tail", "5", "wp1-wordpress",
    ]
    assert "-f" not in logs.compose_logs_command(source, False, None)


def test_show_prefixes_and_tails_files(tmp_path):
    (tmp_path / "serve.log").write_text("a\nb\nc\n")
    (tmp_path / "dashboard.log").write_text("GET /\n")
    found = logs.sources(tmp_path)
    out: list[str] = []
    logs.show([found["serve"], found["dashboard"]], follow=False, tail=2, write=out.append)
    assert out == ["serve     | b\n", "serve     | c\n", "dashboard | GET /\n"]


def test_follow_file_reads_new_lines_and_replaced_file(tmp_path):
    path = tmp_path / "dashboard.log"
    path.write_text("old\n")
    seen: list[str] = []
    got = threading.Event()
    stop = threading.Event()

    def emit(line):
        seen.append(line.rstrip())
        if line.rstrip() == "new file":
            got.set()

    thread = threading.Thread(target=logs.follow_file, args=(path, None, emit, stop), daemon=True)
    thread.start()
    with open(path, "a") as handle:
        handle.write("appended\n")
    import time

    time.sleep(0.5)
    path.replace(tmp_path / "dashboard.log.1")
    path.write_text("new file\n")
    assert got.wait(5)
    stop.set()
    thread.join(2)
    assert seen == ["old", "appended", "new file"]
