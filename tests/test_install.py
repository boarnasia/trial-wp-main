import base64
from pathlib import Path

import pytest

from wp_main import devenv, docker, hosts, trust, versioning
from wp_main.config import SITES
from wp_main.runner import DevEnvError
from wp_main.sites import render_site

PEM = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(b"fake-ca" * 8).decode() + "\n-----END CERTIFICATE-----\n"


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    """ホストのファイルと wp-main を tmp_path に向け、clone はテンプレートの描画で代用する。"""
    main = tmp_path / "wp-main"
    main.mkdir()
    (main / ".env.example").write_text("WP1_DOMAIN=local.wp1.yamashita109.com\n")
    local = main / ".local"
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text("127.0.0.1\tlocalhost\n")

    monkeypatch.setattr(devenv, "MAIN_DIR", main)
    monkeypatch.setattr(hosts, "HOSTS_FILE", hosts_file)
    monkeypatch.setattr(hosts, "BACKUP_FILE", tmp_path / "hosts.bak")
    monkeypatch.setattr(trust, "LOCAL_DIR", local)
    monkeypatch.setattr(trust, "STATE_FILE", local / "state.json")
    monkeypatch.setattr(trust, "CA_CERT_FILE", local / "root.crt")
    monkeypatch.setattr(devenv, "CA_CERT_FILE", local / "root.crt")

    def fake_repo(runner, site, root):
        runner.run(["git", "clone", site.remote, str(root / site.dir_name)])
        render_site(site, root / site.dir_name)
        return "scaffolded"

    monkeypatch.setattr(devenv, "ensure_site_repo", fake_repo)
    return tmp_path, local


def responder(*, installed=False, network=False):
    def respond(args: list[str]) -> tuple[int, str]:
        if args[:3] == ["docker", "network", "inspect"]:
            return (0 if network else 1), ""
        if "is-installed" in args:
            return (0 if installed else 1), ""
        if args[:3] == ["docker", "compose", "cp"]:
            Path(args[-1]).write_text(PEM)
        return 0, ""

    return respond


def index_of(calls: list[list[str]], predicate) -> int:
    for number, call in enumerate(calls):
        if predicate(call):
            return number
    raise AssertionError("expected command was not run")


def has(*parts: str):
    return lambda call: all(part in call for part in parts)


def test_full_flow_order(env, fake_runner, monkeypatch):
    root, local = env
    monkeypatch.setattr(devenv, "check_ports", lambda runner, ports: None)
    runner = fake_runner(responder())
    devenv.install(runner, root, start=True, trust=True)

    calls = runner.calls
    order = [
        index_of(calls, has("git", "clone", SITES[0].remote)),
        index_of(calls, has("git", "clone", SITES[1].remote)),
        index_of(calls, has("network", "create")),
        index_of(calls, has("sudo", "cp", "-p")),
        index_of(calls, lambda call: call[:2] == ["sudo", "cp"] and call[-1] == str(hosts.HOSTS_FILE)),
        index_of(calls, has("compose", "up")),
        index_of(calls, has("core", "install", f"--url=https://{SITES[0].domain}")),
        index_of(calls, has("core", "install", f"--url=https://{SITES[1].domain}")),
        index_of(calls, has("security", "add-trusted-cert")),
    ]
    assert order == sorted(order)
    for site in SITES:
        assert (root / site.dir_name / ".env").exists()
    assert (root / "wp-main" / ".env").exists()
    assert "ca_sha1" in trust.load_state()


def test_no_start_stops_after_hosts(env, fake_runner):
    root, _ = env
    runner = fake_runner(responder())
    devenv.install(runner, root, start=False, trust=True)
    assert runner.mutating(["sudo", "cp"])
    assert not [call for call in runner.calls if "compose" in call]
    assert not runner.mutating(["sudo", "security"])


def test_skip_trust(env, fake_runner, monkeypatch):
    root, _ = env
    monkeypatch.setattr(devenv, "check_ports", lambda runner, ports: None)
    runner = fake_runner(responder())
    devenv.install(runner, root, start=True, trust=False)
    assert runner.mutating(["docker", "compose", "up"])
    assert not [call for call in runner.calls if "security" in call]


def test_busy_port_aborts_before_compose_up(env, fake_runner, monkeypatch):
    root, _ = env
    monkeypatch.setattr(
        devenv, "check_ports", lambda runner, ports: docker.check_ports(runner, ports, is_free=lambda port: False)
    )
    runner = fake_runner(responder())
    with pytest.raises(DevEnvError, match="使用中"):
        devenv.install(runner, root, start=True, trust=True)
    assert not runner.mutating(["docker", "compose", "up"])


def test_installed_site_is_not_reinstalled(env, fake_runner, monkeypatch):
    root, _ = env
    monkeypatch.setattr(devenv, "check_ports", lambda runner, ports: None)
    runner = fake_runner(responder(installed=True, network=True))
    devenv.install(runner, root, start=True, trust=True)
    assert not [call for call in runner.calls if "install" in call and "core" in call]
    assert not runner.mutating(["docker", "network", "create"])


def test_fresh_install_records_latest(env, fake_runner, monkeypatch):
    root, _ = env
    monkeypatch.setattr(devenv, "check_ports", lambda runner, ports: None)
    monkeypatch.setattr(versioning, "latest", lambda: 3)
    devenv.install(fake_runner(responder()), root, start=True, trust=True)
    assert trust.load_state()["env_version"] == 3


def test_existing_install_keeps_version(env, fake_runner, monkeypatch, capsys):
    root, _ = env
    (root / SITES[0].dir_name).mkdir()
    trust.update_state(env_version=1)
    monkeypatch.setattr(versioning, "latest", lambda: 3)
    devenv.install(fake_runner(responder()), root, start=False, trust=True)
    assert trust.load_state()["env_version"] == 1
    assert "devenv migrate" in capsys.readouterr().out


def test_install_enables_hooks(env, fake_runner):
    root, _ = env
    runner = fake_runner(responder())
    devenv.install(runner, root, start=False, trust=True)
    assert [call for call in runner.calls if call[-2:] == ["core.hooksPath", ".githooks"]]
