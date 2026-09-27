import json

import pytest

from wp_main import devenv, health, operations, versioning
from wp_main.health import FAIL, OK, WARN
from wp_main.runner import DevEnvError


def outcomes(*statuses):
    return [health.Outcome(str(i), "config", str(i), status, "m", "h") for i, status in enumerate(statuses)]


def test_check_health_records_counts(monkeypatch, manage, recorded_operations):
    monkeypatch.setattr(health, "run_health", lambda ctx: outcomes(OK, FAIL))
    result = manage("devenv", "check-health")
    assert result.exit_code == 1
    [entry] = recorded_operations
    assert entry["command"] == "check-health" and entry["exit_code"] == 1 and entry["succeeded"] is False
    assert entry["summary"] == "OK 1 / WARN 0 / FAIL 1 / SKIP 0"


def test_check_health_json_stays_json_when_recording_fails(monkeypatch, manage):
    def down(payload):
        raise OSError("database is locked")

    monkeypatch.setattr(operations, "write", down)
    monkeypatch.setattr(health, "run_health", lambda ctx: outcomes(OK, WARN))
    result = manage("devenv", "check-health", "--json")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True
    assert "操作履歴を記録できませんでした" in result.stderr


def test_migrate_records_applied(monkeypatch, manage, recorded_operations):
    def migrate(*args, report, **kwargs):
        report(3, 4, None)
        return 0

    monkeypatch.setattr(versioning, "migrate", migrate)
    assert manage("devenv", "migrate").exit_code == 0
    [entry] = recorded_operations
    assert (entry["command"], entry["summary"], entry["succeeded"]) == ("migrate", "3 → 4", True)


def test_migrate_auto_failure_is_recorded_as_failure(monkeypatch, manage, recorded_operations):
    def migrate(*args, report, **kwargs):
        report(3, 3, "migration 4 (m0004) が失敗しました: boom")
        return 0

    monkeypatch.setattr(versioning, "migrate", migrate)
    assert manage("devenv", "migrate", "--auto").exit_code == 0
    [entry] = recorded_operations
    assert entry["exit_code"] == 0 and entry["succeeded"] is False
    assert entry["summary"].startswith("3 → 3: migration 4")


def test_migrate_without_changes_is_not_recorded(monkeypatch, manage, recorded_operations):
    monkeypatch.setattr(versioning, "migrate", lambda *args, **kwargs: 0)
    manage("devenv", "migrate", "--auto")
    assert recorded_operations == []


def test_install_records_result(monkeypatch, manage, recorded_operations):
    monkeypatch.setattr(devenv, "install", lambda *a, **k: None)
    assert manage("devenv", "install", "--skip-trust").exit_code == 0
    [entry] = recorded_operations
    assert entry["command"] == "install" and entry["succeeded"] and entry["options"]["skip_trust"] is True


def test_install_failure_is_recorded(monkeypatch, manage, recorded_operations):
    def fail(*args, **kwargs):
        raise DevEnvError("clone に失敗しました")

    monkeypatch.setattr(devenv, "install", fail)
    assert manage("devenv", "install").exit_code == 1
    assert recorded_operations[0]["summary"] == "clone に失敗しました"


@pytest.mark.parametrize("command", [("install", "--dry-run"), ("uninstall", "--dry-run")])
def test_dry_run_and_uninstall_are_not_recorded(monkeypatch, manage, recorded_operations, command):
    monkeypatch.setattr(devenv, "install", lambda *a, **k: None)
    monkeypatch.setattr(devenv, "uninstall", lambda *a, **k: None)
    manage("devenv", *command)
    assert recorded_operations == []


def test_real_migrate_reports_only_when_applied(tmp_path, monkeypatch, fake_runner):
    from wp_main import trust

    monkeypatch.setattr(trust, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(trust, "LOCAL_DIR", tmp_path)
    trust.update_state(env_version=versioning.latest())
    reports = []
    versioning.migrate(fake_runner(), tmp_path, report=lambda *a: reports.append(a))
    assert reports == []
