from pathlib import Path

import pytest

from wp_main import trust, versioning
from wp_main.hosts import BEGIN, with_block
from wp_main.devenv.migrations import m0002_dashboard
from wp_main.versioning import MigrationContext

OLD_DOMAINS = ["local.wp1.yamashita109.com", "local.wp2.yamashita109.com"]


@pytest.fixture
def hosts_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "hosts"
    path.write_text(with_block("127.0.0.1\tlocalhost\n", OLD_DOMAINS))
    monkeypatch.setattr(m0002_dashboard.hosts, "HOSTS_FILE", path)
    monkeypatch.setattr(m0002_dashboard.hosts, "BACKUP_FILE", tmp_path / "hosts.bak")
    return path


def context(runner, tmp_path):
    return MigrationContext(runner, tmp_path, tmp_path / "wp-main", ())


def caddy(running: bool):
    def respond(args):
        if args[:3] == ["docker", "compose", "ps"]:
            return 0, "abc123\n" if running else ""
        return 0, ""

    return respond


def test_needs_sudo():
    assert m0002_dashboard.REQUIRES_SUDO and not m0002_dashboard.DESTRUCTIVE


def test_running_environment_is_rebuilt(fake_runner, hosts_file, tmp_path):
    runner = fake_runner(caddy(running=True))
    m0002_dashboard.up(context(runner, tmp_path))
    assert runner.mutating(["sudo", "cp"])
    assert ["docker", "compose", "up", "-d", "--wait", "caddy"] in runner.calls


def test_stopped_environment_is_not_started(fake_runner, hosts_file, tmp_path):
    runner = fake_runner(caddy(running=False))
    m0002_dashboard.up(context(runner, tmp_path))
    assert runner.mutating(["sudo", "cp"])
    assert not runner.mutating(["docker", "compose", "up"])


def test_rerun_keeps_hosts(fake_runner, hosts_file, tmp_path):
    from wp_main.devenv import hosts_domains

    hosts_file.write_text(with_block("127.0.0.1\tlocalhost\n", hosts_domains()))
    runner = fake_runner(caddy(running=False))
    m0002_dashboard.up(context(runner, tmp_path))
    assert runner.mutating(["sudo"]) == []
    assert hosts_file.read_text().count(BEGIN) == 1


def test_auto_does_not_run(fake_runner, tmp_path, monkeypatch, capsys):
    local = tmp_path / "wp-main" / ".local"
    monkeypatch.setattr(trust, "LOCAL_DIR", local)
    monkeypatch.setattr(trust, "STATE_FILE", local / "state.json")
    (tmp_path / "wp-wp1").mkdir()
    runner = fake_runner()
    assert versioning.migrate(runner, tmp_path, auto=True, main_dir=tmp_path / "wp-main") == 0
    assert "sudo が必要な migration があります" in capsys.readouterr().out
    assert trust.load_state().get("env_version") is None
