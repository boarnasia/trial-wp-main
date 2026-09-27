import pytest
import typer

from wp_main import devenv


def test_declined_confirmation_does_nothing(tmp_path, fake_runner, monkeypatch):
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: False)
    monkeypatch.setattr(devenv, "load_state", lambda: {})
    (tmp_path / "wp-wp1").mkdir()
    runner = fake_runner()
    with pytest.raises(typer.Exit):
        devenv.uninstall(runner, tmp_path, assume_yes=False)
    assert (tmp_path / "wp-wp1").exists()
    assert runner.calls == []


def test_unpushed_commits_warned(tmp_path, fake_runner):
    (tmp_path / ".git").mkdir()
    runner = fake_runner(lambda args: (0, "abc123 init\n" if "log" in args else ""))
    assert devenv.unsaved_changes(runner, tmp_path) == ["未 push のコミット 1 件"]


def test_backup_removal_is_suggested(tmp_path, fake_runner, monkeypatch, capsys):
    backup = tmp_path / "hosts.wp-dev-env.bak"
    backup.write_text("")
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("127.0.0.1\tlocalhost\n")
    monkeypatch.setattr(devenv.hosts, "BACKUP_FILE", backup)
    monkeypatch.setattr(devenv.hosts, "HOSTS_FILE", hosts_file)
    monkeypatch.setattr(devenv, "load_state", lambda: {})
    monkeypatch.setattr(devenv, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(devenv, "CA_CERT_FILE", tmp_path / "root.crt")
    monkeypatch.setattr(devenv, "MAIN_DIR", tmp_path)

    devenv.uninstall(fake_runner(lambda args: (1, "")), tmp_path, assume_yes=True)
    assert f"sudo rm {backup}" in capsys.readouterr().out
    assert backup.exists()


def test_db_and_legacy_dashboard_removed(tmp_path, fake_runner, monkeypatch):
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("127.0.0.1\tlocalhost\n")
    monkeypatch.setattr(devenv.hosts, "BACKUP_FILE", tmp_path / "hosts.bak")
    monkeypatch.setattr(devenv.hosts, "HOSTS_FILE", hosts_file)
    monkeypatch.setattr(devenv, "load_state", lambda: {})
    monkeypatch.setattr(devenv, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(devenv, "CA_CERT_FILE", tmp_path / "root.crt")
    monkeypatch.setattr(devenv, "MAIN_DIR", tmp_path)

    local = tmp_path / ".local"
    (local / "locks").mkdir(parents=True)
    for name in ("db.sqlite3", "db.sqlite3-wal"):
        (local / name).write_text("")

    runner = fake_runner()
    devenv.uninstall(runner, tmp_path, assume_yes=True)
    assert not (local / "db.sqlite3").exists() and not (local / "db.sqlite3-wal").exists()
    assert not (local / "locks").exists()
    assert ["docker", "rm", "-f", "wp-dashboard"] in runner.calls
    assert ["docker", "rm", "-f", "wp1-db"] in runner.calls and ["docker", "rm", "-f", "wp2-db"] in runner.calls
    assert ["docker", "compose", "down", "--volumes", "--remove-orphans"] in runner.calls
    assert ["docker", "network", "rm", "wp-db"] in runner.calls
    assert ["docker", "image", "rm", "wp-main-dashboard"] in runner.calls
    [volumes] = runner.mutating(["docker", "volume", "rm"])
    assert {"wp-dashboard-data", "wp-mysql-data", "wp1-db-data", "wp2-db-data"} <= set(volumes)


def test_running_serve_is_warned(tmp_path, fake_runner, monkeypatch, capsys):
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: False)
    monkeypatch.setattr(devenv, "load_state", lambda: {})
    monkeypatch.setattr(devenv, "dashboard_running", lambda: True)
    with pytest.raises(typer.Exit):
        devenv.uninstall(fake_runner(), tmp_path, assume_yes=False)
    assert "uv run manage.py serve が動いています" in capsys.readouterr().out
