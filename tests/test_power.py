import json
import subprocess
from pathlib import Path

import pytest

from wp_main import power
from wp_main.config import SITES
from wp_main.runner import DevEnvError

WP1, WP2 = SITES


def item(name: str, status: str = "running", health: str | None = None) -> dict:
    state = {"Status": status}
    if health:
        state["Health"] = {"Status": health}
    return {"Name": f"/{name}", "State": state}


MYSQL_OK = item("wp-mysql", health="healthy")


class InspectRunner:
    def __init__(self, items, code=0, stderr=""):
        self.items, self.code, self.stderr = items, code, stderr
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, args, *, cwd=None, check=True, capture=False, mutate=True, env=None):
        self.calls.append((list(args), cwd))
        if args[:2] == ["docker", "inspect"]:
            found = [entry for entry in self.items if entry["Name"].lstrip("/") in args[2:]]
            return subprocess.CompletedProcess(args, self.code, json.dumps(found), self.stderr)
        return subprocess.CompletedProcess(args, 0, "", "")

    def mutations(self) -> list[list[str]]:
        return [args for args, _ in self.calls if args[:2] != ["docker", "inspect"]]


@pytest.fixture
def root(tmp_path):
    (tmp_path / "wp-wp1").mkdir()
    (tmp_path / "wp-wp1" / ".env").write_text("WP_HOME=x\n")
    return tmp_path


def state(items, **kwargs):
    return power.inspect(InspectRunner(items, **kwargs), WP1)


def test_running():
    result = state([item("wp1-wordpress"), MYSQL_OK])
    assert (result.state, result.label) == (power.RUNNING, "起動中")


def test_stopped_when_missing():
    result = state([MYSQL_OK], code=1, stderr="Error: No such object: wp1-wordpress")
    assert result.state == power.STOPPED


def test_stopped_when_exited_even_if_mysql_runs():
    assert state([item("wp1-wordpress", "exited"), MYSQL_OK]).state == power.STOPPED


def test_partial_when_mysql_unhealthy():
    result = state([item("wp1-wordpress"), item("wp-mysql", health="starting")])
    assert result.state == power.PARTIAL and "wp-mysql" in result.detail


def test_unknown_when_docker_down():
    result = state([], code=1, stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock")
    assert result.state == power.UNKNOWN


def test_running_sites():
    runner = InspectRunner([item("wp1-wordpress", "exited"), item("wp2-wordpress")])
    assert power.running_sites(runner) == [WP2]


def test_start_prepares_schema_then_starts_wordpress(root):
    runner = InspectRunner([MYSQL_OK])
    power.start(runner, WP1, root, main_dir=root / "wp-main")
    mysql_up, schema, wordpress_up = runner.mutations()
    assert mysql_up == ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "mysql"]
    assert schema[:4] == ["docker", "exec", "wp-mysql", "sh"]
    assert "`wp1`" in schema[-1].replace("\\`", "`")
    assert wordpress_up == ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "wp1-wordpress"]
    assert {cwd for args, cwd in runner.calls if args[:2] == ["docker", "compose"]} == {root / "wp-main"}


def test_schema_command_has_no_password(root):
    (root / "wp-wp1" / ".env").write_text("WP_DB_NAME=wp1_dev\nWP_ADMIN_PASSWORD=secret-admin\n")
    runner = InspectRunner([MYSQL_OK])
    power.ensure_schema(runner, WP1, root)
    (args, _), = runner.calls
    assert "`wp1_dev`" in args[-1].replace("\\`", "`")
    assert "$MYSQL_ROOT_PASSWORD" in args[-1] and "secret" not in " ".join(args)


def test_schema_name_rejects_unsafe(root):
    (root / "wp-wp1" / ".env").write_text("WP_DB_NAME=wp1`; DROP\n")
    with pytest.raises(DevEnvError, match="WP_DB_NAME"):
        power.schema_name(WP1, root)


def test_stop_only_wordpress(root):
    runner = InspectRunner([item("wp1-wordpress"), MYSQL_OK])
    power.stop(runner, WP1, root, main_dir=root / "wp-main")
    assert runner.mutations() == [["docker", "compose", "stop", "wp1-wordpress"]]


def test_start_infra():
    runner = InspectRunner([])
    power.start_infra(runner)
    assert runner.mutations() == [["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "caddy", "mysql"]]


def test_start_without_env_does_nothing(root):
    (root / "wp-wp1" / ".env").unlink()
    runner = InspectRunner([])
    with pytest.raises(DevEnvError, match=".env がありません"):
        power.start(runner, WP1, root)
    assert runner.calls == []


def test_lock_rejects_second_holder(tmp_path):
    with power.site_lock(WP1, tmp_path):
        assert power.is_busy(WP1, tmp_path)
        with pytest.raises(power.Busy):
            with power.site_lock(WP1, tmp_path):
                pass
    assert not power.is_busy(WP1, tmp_path)
