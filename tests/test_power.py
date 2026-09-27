import json
import subprocess
from pathlib import Path

import pytest

from wp_main.config import SITES
from wp_main.dashboard import power
from wp_main.runner import DevEnvError

WP1 = SITES[0]


def item(name: str, status: str = "running", project: str = "wp-main") -> dict:
    return {"Name": f"/{name}", "State": {"Status": status},
            "Config": {"Labels": {"com.docker.compose.project": project}}}


class InspectRunner:
    def __init__(self, items, code=0, stderr=""):
        self.items, self.code, self.stderr = items, code, stderr
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, args, *, cwd=None, check=True, capture=False, mutate=True):
        self.calls.append((list(args), cwd))
        if args[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(args, self.code, json.dumps(self.items), self.stderr)
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def root(tmp_path):
    (tmp_path / "wp-wp1").mkdir()
    (tmp_path / "wp-wp1" / ".env").write_text("WP_HOME=x\n")
    return tmp_path


def state(items, root, **kwargs):
    return power.inspect(InspectRunner(items, **kwargs), WP1, root, main_dir=root / "wp-main")


def test_running(root):
    result = state([item("wp1-wordpress"), item("wp1-db")], root)
    assert (result.state, result.label, result.project_dir) == (power.RUNNING, "起動中", root / "wp-main")


def test_stopped_when_missing(root):
    result = state([], root, code=1, stderr="Error: No such object: wp1-wordpress")
    assert result.state == power.STOPPED


def test_partial(root):
    assert state([item("wp1-wordpress", "exited"), item("wp1-db")], root).state == power.PARTIAL


def test_unknown_when_docker_down(root):
    result = state([], root, code=1, stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock")
    assert result.state == power.UNKNOWN and "Cannot connect" in result.detail


def test_solo_project_uses_site_dir(root):
    result = state([item("wp1-wordpress", "exited", "wp-wp1"), item("wp1-db", "exited", "wp-wp1")], root)
    assert result.project_dir == root / "wp-wp1"


def test_start_uses_main_project(root):
    runner = InspectRunner([], code=1, stderr="Error: No such object: wp1-wordpress")
    power.start(runner, WP1, root, main_dir=root / "wp-main")
    args, cwd = runner.calls[-1]
    assert args == ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120", "wp1-wordpress"]
    assert cwd == root / "wp-main"


def test_stop_in_solo_project(root):
    runner = InspectRunner([item("wp1-wordpress", project="wp-wp1"), item("wp1-db", project="wp-wp1")])
    power.stop(runner, WP1, root, main_dir=root / "wp-main")
    args, cwd = runner.calls[-1]
    assert args == ["docker", "compose", "stop", "wp1-wordpress", "wp1-db"]
    assert cwd == root / "wp-wp1"


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
