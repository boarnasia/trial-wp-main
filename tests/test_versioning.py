import importlib
import itertools
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wp_main import cli, devenv, trust, versioning
from wp_main.config import SITES
from wp_main.runner import DevEnvError

COUNTER = itertools.count()
TEMPLATE = """VERSION = {version}
DESCRIPTION = "test {version}"
REQUIRES_SUDO = {sudo}
DESTRUCTIVE = {destructive}
LOSES = "test data"


def up(ctx):
    if {fail}:
        raise RuntimeError("boom {version}")
    (ctx.main_dir / "applied.txt").open("a").write("{version}\\n")
"""


@pytest.fixture
def state(tmp_path: Path, monkeypatch):
    local = tmp_path / "wp-main" / ".local"
    local.parent.mkdir()
    monkeypatch.setattr(trust, "LOCAL_DIR", local)
    monkeypatch.setattr(trust, "STATE_FILE", local / "state.json")
    return tmp_path


@pytest.fixture
def make_package(tmp_path: Path, monkeypatch):
    """テスト用の migration パッケージを作って import する。"""
    monkeypatch.syspath_prepend(str(tmp_path))

    def make(*specs: dict, names: list[str] | None = None):
        name = f"fake_migrations_{next(COUNTER)}"
        directory = tmp_path / name
        directory.mkdir()
        (directory / "__init__.py").write_text("")
        for index, spec in enumerate(specs):
            version = spec.get("version", index + 2)
            filename = names[index] if names else f"m{version:04d}_step"
            (directory / f"{filename}.py").write_text(
                TEMPLATE.format(
                    version=version,
                    sudo=spec.get("sudo", False),
                    destructive=spec.get("destructive", False),
                    fail=spec.get("fail", False),
                )
            )
        importlib.invalidate_caches()
        return importlib.import_module(name)

    return make


def applied(root: Path) -> list[str]:
    path = root / "wp-main" / "applied.txt"
    return path.read_text().split() if path.exists() else []


def run(fake_runner, root, package, **kwargs):
    kwargs.setdefault("is_tty", lambda: True)
    return versioning.migrate(fake_runner(), root, package=package, main_dir=root / "wp-main", **kwargs)


# 1.1 / 1.2


def test_update_state_keeps_other_keys(state):
    trust.update_state(ca_sha1="ABC")
    trust.update_state(env_version=2)
    assert trust.load_state() == {"ca_sha1": "ABC", "env_version": 2}


def test_installed_version(state):
    root = state
    assert versioning.installed_version(root) is None
    (root / SITES[0].dir_name).mkdir()
    assert versioning.installed_version(root) == 1
    trust.update_state(env_version=4)
    assert versioning.installed_version(root) == 4


# 1.3


def test_discover_orders_and_latest(make_package):
    package = make_package({"version": 3}, {"version": 2})
    found = versioning.discover(package)
    assert [module.VERSION for module in found] == [2, 3]
    assert versioning.latest_version(found) == 3
    assert versioning.latest_version([]) == 1


def test_real_package_is_valid():
    versioning.discover()


@pytest.mark.parametrize(
    ("specs", "names", "message"),
    [
        ([{"version": 2}, {"version": 4}], None, "連番"),
        ([{"version": 3}], None, "連番"),
        ([{"version": 2}], ["m0003_wrong"], "一致しません"),
        ([{"version": 2}], ["badname"], "ファイル名"),
    ],
)
def test_discover_rejects_invalid(make_package, specs, names, message):
    with pytest.raises(DevEnvError, match=message):
        versioning.discover(make_package(*specs, names=names))


# 2.1 / 2.2


def test_not_installed(state, fake_runner, make_package):
    assert run(fake_runner, state, make_package({})) == 1
    assert run(fake_runner, state, make_package({}), auto=True) == 0


def test_up_to_date(state, fake_runner, make_package):
    trust.update_state(env_version=2)
    assert run(fake_runner, state, make_package({})) == 0
    assert applied(state) == []


def test_newer_than_code(state, fake_runner, make_package):
    trust.update_state(env_version=9)
    assert run(fake_runner, state, make_package({})) == 1
    assert trust.load_state()["env_version"] == 9


def test_applies_pending_in_order(state, fake_runner, make_package):
    trust.update_state(env_version=1)
    assert run(fake_runner, state, make_package({}, {})) == 0
    assert applied(state) == ["2", "3"]
    assert trust.load_state()["env_version"] == 3


def test_stops_on_failure(state, fake_runner, make_package, capsys):
    trust.update_state(env_version=1)
    assert run(fake_runner, state, make_package({}, {"fail": True}, {})) == 1
    assert applied(state) == ["2"]
    assert trust.load_state()["env_version"] == 2
    assert "boom 3" in capsys.readouterr().out


def test_dry_run_changes_nothing(state, make_package, fake_runner):
    trust.update_state(env_version=1)
    runner = fake_runner(dry_run=True)
    assert versioning.migrate(runner, state, package=make_package({}), main_dir=state / "wp-main") == 0
    assert applied(state) == [] and trust.load_state()["env_version"] == 1


# 2.3


@pytest.mark.parametrize(
    ("spec", "docker_ok"),
    [({"sudo": True}, True), ({"destructive": True}, True), ({}, False)],
)
def test_auto_refuses(state, fake_runner, make_package, spec, docker_ok):
    trust.update_state(env_version=1)
    runner = fake_runner(lambda args: (0 if docker_ok else 1, ""))
    code = versioning.migrate(runner, state, auto=True, package=make_package(spec), main_dir=state / "wp-main")
    assert code == 0
    assert applied(state) == [] and trust.load_state()["env_version"] == 1


def test_auto_applies_safe_migrations(state, fake_runner, make_package):
    trust.update_state(env_version=1)
    assert run(fake_runner, state, make_package({}), auto=True) == 0
    assert trust.load_state()["env_version"] == 2


def test_auto_failure_exits_zero(state, fake_runner, make_package):
    trust.update_state(env_version=1)
    assert run(fake_runner, state, make_package({"fail": True}), auto=True) == 0


# 2.4


def test_destructive_needs_confirmation(state, fake_runner, make_package, monkeypatch, capsys):
    trust.update_state(env_version=1)
    monkeypatch.setattr(versioning.typer, "confirm", lambda *a, **k: False)
    assert run(fake_runner, state, make_package({"destructive": True})) == 1
    assert applied(state) == []
    assert "test data" in capsys.readouterr().out
    assert run(fake_runner, state, make_package({"destructive": True}), assume_yes=True) == 0
    assert applied(state) == ["2"]


def test_sudo_without_tty_stops(state, fake_runner, make_package):
    trust.update_state(env_version=1)
    assert run(fake_runner, state, make_package({"sudo": True}), is_tty=lambda: False) == 1
    assert applied(state) == []


# 3.2


@pytest.mark.parametrize(
    ("current", "expect_set"),
    [("", True), (".githooks", False), ("custom-hooks", False)],
)
def test_enable_hooks(fake_runner, current, expect_set, capsys):
    runner = fake_runner(lambda args: (0, current + "\n"))
    devenv.enable_hooks(runner)
    sets = [call for call in runner.calls if call[-2:] == ["core.hooksPath", ".githooks"]]
    assert bool(sets) == expect_set
    if current == "custom-hooks":
        assert "変更しません" in capsys.readouterr().out


@pytest.mark.parametrize(("current", "expect_unset"), [(".githooks", True), ("custom-hooks", False), ("", False)])
def test_disable_hooks(fake_runner, current, expect_unset):
    runner = fake_runner(lambda args: (0, current + "\n"))
    devenv.disable_hooks(runner)
    assert bool([call for call in runner.calls if "--unset" in call]) == expect_unset


# 3.3


def test_outdated_warning(monkeypatch):
    monkeypatch.setattr(versioning, "outdated_message", lambda root: "OUTDATED")
    monkeypatch.setattr(devenv, "uninstall", lambda *a, **k: print("uninstall ran"))
    result = CliRunner().invoke(cli.app, ["dev-env:uninstall", "--dry-run"])
    assert "OUTDATED" in result.stderr
    assert "uninstall ran" in result.stdout


@pytest.mark.parametrize("command", ["dev-env:migrate", "dev-env:check-health", "help", "version"])
def test_no_warning_for_exempt_commands(monkeypatch, command):
    monkeypatch.setattr(versioning, "outdated_message", lambda root: "OUTDATED")
    monkeypatch.setattr(versioning, "migrate", lambda *a, **k: 0)
    monkeypatch.setattr(cli.health, "run_health", lambda ctx: [])
    result = CliRunner().invoke(cli.app, [command])
    assert "OUTDATED" not in result.stderr


def test_auto_survives_broken_migration(monkeypatch):
    def broken(*args, **kwargs):
        raise SyntaxError("invalid syntax in m0002")

    monkeypatch.setattr(versioning, "migrate", broken)
    result = CliRunner().invoke(cli.app, ["dev-env:migrate", "--auto"])
    assert result.exit_code == 0
    assert "m0002" in result.stderr


def test_warning_failure_does_not_block_command(monkeypatch):
    def broken(root):
        raise ImportError("cannot import m0002")

    monkeypatch.setattr(versioning, "outdated_message", broken)
    monkeypatch.setattr(devenv, "uninstall", lambda *a, **k: print("uninstall ran"))
    result = CliRunner().invoke(cli.app, ["dev-env:uninstall", "--dry-run"])
    assert result.exit_code == 0
    assert "uninstall ran" in result.stdout
    assert "確認できません" in result.stderr
