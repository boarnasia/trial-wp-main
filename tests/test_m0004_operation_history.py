from pathlib import Path

import pytest

from wp_main import trust, versioning
from wp_main.devenv.migrations import m0004_operation_history
from wp_main.sites import parse_env
from wp_main.versioning import MigrationContext


@pytest.fixture
def main_dir(tmp_path: Path) -> Path:
    path = tmp_path / "wp-main"
    path.mkdir()
    (path / ".env").write_text("WP1_DOMAIN=local.wp1.yamashita109.com")
    return path


def context(runner, main_dir):
    return MigrationContext(runner, main_dir.parent, main_dir, ())


def caddy(running: bool):
    def respond(args):
        if args[:3] == ["docker", "compose", "ps"]:
            return 0, "abc123\n" if running else ""
        return 0, ""

    return respond


def test_is_latest_and_runs_automatically():
    assert versioning.latest() >= 4
    assert not m0004_operation_history.REQUIRES_SUDO and not m0004_operation_history.DESTRUCTIVE


def test_adds_secret_key_and_rebuilds(fake_runner, main_dir):
    runner = fake_runner(caddy(running=True))
    m0004_operation_history.up(context(runner, main_dir))
    env = parse_env((main_dir / ".env").read_text())
    assert env["WP1_DOMAIN"] == "local.wp1.yamashita109.com"
    assert len(env["DASHBOARD_API_TOKEN"]) >= 50
    assert ["docker", "compose", "up", "-d", "--wait", "caddy"] in runner.calls


def test_keeps_existing_key(fake_runner, main_dir):
    (main_dir / ".env").write_text("DASHBOARD_API_TOKEN=keep\n")
    m0004_operation_history.up(context(fake_runner(caddy(running=True)), main_dir))
    assert (main_dir / ".env").read_text() == "DASHBOARD_API_TOKEN=keep\n"


def test_replaces_empty_key_value(fake_runner, main_dir):
    (main_dir / ".env").write_text("DASHBOARD_API_TOKEN=\n")
    m0004_operation_history.up(context(fake_runner(caddy(running=False)), main_dir))
    assert parse_env((main_dir / ".env").read_text())["DASHBOARD_API_TOKEN"]


def test_stopped_environment_is_not_started(fake_runner, main_dir):
    runner = fake_runner(caddy(running=False))
    m0004_operation_history.up(context(runner, main_dir))
    assert "DASHBOARD_API_TOKEN" in (main_dir / ".env").read_text()
    assert not runner.mutating(["docker", "compose", "up"])


def test_dry_run_changes_nothing(fake_runner, main_dir):
    before = (main_dir / ".env").read_text()
    runner = fake_runner(caddy(running=True), dry_run=True)
    m0004_operation_history.up(context(runner, main_dir))
    assert (main_dir / ".env").read_text() == before


def test_auto_runs(fake_runner, main_dir, monkeypatch):
    local = main_dir / ".local"
    monkeypatch.setattr(trust, "LOCAL_DIR", local)
    monkeypatch.setattr(trust, "STATE_FILE", local / "state.json")
    trust.update_state(env_version=3)
    (main_dir.parent / "wp-wp1").mkdir()
    # 後の migration の前提（サイトの .env など）はこのテストの対象外なので、この版までに限る
    found = versioning.discover()
    monkeypatch.setattr(versioning, "discover", lambda *args: [module for module in found if module.VERSION <= 4])
    runner = fake_runner(caddy(running=True))
    assert versioning.migrate(runner, main_dir.parent, auto=True, main_dir=main_dir) == 0
    assert trust.load_state()["env_version"] == 4
    assert "DASHBOARD_API_TOKEN" in (main_dir / ".env").read_text()
