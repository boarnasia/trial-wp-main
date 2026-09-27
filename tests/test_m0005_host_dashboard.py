import sqlite3
from pathlib import Path

import pytest

from wp_main import trust, versioning
from wp_main.devenv.migrations import m0005_host_dashboard
from wp_main.runner import DevEnvError
from wp_main.versioning import MigrationContext

VOLUME = "wp-dashboard-data"


@pytest.fixture
def main_dir(tmp_path: Path) -> Path:
    path = tmp_path / "wp-main"
    path.mkdir()
    return path


def context(runner, main_dir):
    return MigrationContext(runner, main_dir.parent, main_dir, ())


def make_db(path: Path, rows: int = 1) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("create table t (x)")
        connection.executemany("insert into t values (?)", [(i,) for i in range(rows)])


def legacy(main_dir: Path, *, running=True, exists=True, copy=lambda out: make_db(out / "db.sqlite3", 3), copy_code=0):
    """旧ダッシュボードのリソースがある環境。docker run の cp は copy で代用する。"""

    def respond(args):
        if args[:3] == ["docker", "compose", "ps"]:
            return 0, "abc123\n" if running else ""
        if args[:2] == ["docker", "run"]:
            if copy_code == 0:
                copy(main_dir / ".local")
            return copy_code, ""
        if args[1:3] == ["container", "inspect"] or args[1:3] == ["volume", "inspect"] or args[1:3] == ["image", "inspect"]:
            return (0 if exists else 1), ""
        return 0, ""

    return respond


def test_is_latest_and_runs_automatically():
    assert versioning.latest() == 5
    assert not m0005_host_dashboard.REQUIRES_SUDO and not m0005_host_dashboard.DESTRUCTIVE


def test_copies_history_then_removes_legacy(fake_runner, main_dir):
    runner = fake_runner(legacy(main_dir))
    m0005_host_dashboard.up(context(runner, main_dir))
    with sqlite3.connect(main_dir / ".local" / "db.sqlite3") as connection:
        assert connection.execute("select count(*) from t").fetchone()[0] == 3
    order = [call[:3] for call in runner.calls if call[:2] in (["docker", "rm"], ["docker", "run"], ["docker", "volume"], ["docker", "image"])]
    assert ["docker", "rm", "-f"] in order
    assert order.index(["docker", "run", "--rm"]) < order.index(["docker", "volume", "rm"])
    assert ["docker", "image", "rm", "wp-main-dashboard"] in runner.calls
    assert ["docker", "compose", "up", "-d", "--build", "--wait"] in runner.calls


def test_existing_db_is_kept(fake_runner, main_dir):
    (main_dir / ".local").mkdir()
    make_db(main_dir / ".local" / "db.sqlite3", 7)
    runner = fake_runner(legacy(main_dir))
    m0005_host_dashboard.up(context(runner, main_dir))
    assert not runner.mutating(["docker", "run"])
    assert ["docker", "volume", "rm", VOLUME] in runner.calls
    with sqlite3.connect(main_dir / ".local" / "db.sqlite3") as connection:
        assert connection.execute("select count(*) from t").fetchone()[0] == 7


def test_broken_copy_keeps_volume(fake_runner, main_dir):
    runner = fake_runner(legacy(main_dir, copy=lambda out: (out / "db.sqlite3").write_bytes(b"not a database" * 100)))
    with pytest.raises(DevEnvError, match="検証できません"):
        m0005_host_dashboard.up(context(runner, main_dir))
    assert ["docker", "volume", "rm", VOLUME] not in runner.calls
    assert not (main_dir / ".local" / "db.sqlite3").exists()


def test_failed_copy_keeps_volume(fake_runner, main_dir):
    runner = fake_runner(legacy(main_dir, copy_code=1))
    with pytest.raises(DevEnvError):
        m0005_host_dashboard.up(context(runner, main_dir))
    assert ["docker", "volume", "rm", VOLUME] not in runner.calls


def test_rerun_without_legacy_resources(fake_runner, main_dir):
    runner = fake_runner(legacy(main_dir, exists=False))
    m0005_host_dashboard.up(context(runner, main_dir))
    assert not runner.mutating(["docker", "rm"]) and not runner.mutating(["docker", "volume", "rm"])
    assert not (main_dir / ".local" / "db.sqlite3").exists()


def test_stopped_environment_is_not_started(fake_runner, main_dir):
    runner = fake_runner(legacy(main_dir, running=False))
    m0005_host_dashboard.up(context(runner, main_dir))
    assert ["docker", "volume", "rm", VOLUME] in runner.calls
    assert not runner.mutating(["docker", "compose", "up"])


def test_auto_runs(fake_runner, main_dir, monkeypatch):
    local = main_dir / ".local"
    monkeypatch.setattr(trust, "LOCAL_DIR", local)
    monkeypatch.setattr(trust, "STATE_FILE", local / "state.json")
    trust.update_state(env_version=4)
    (main_dir.parent / "wp-wp1").mkdir()
    runner = fake_runner(legacy(main_dir))
    assert versioning.migrate(runner, main_dir.parent, auto=True, main_dir=main_dir) == 0
    assert trust.load_state()["env_version"] == 5
