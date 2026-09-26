import base64
import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wp_main import cli, health
from wp_main.config import SITES
from wp_main.health import FAIL, OK, SKIP, WARN, Check, HealthContext, Result, evaluate
from wp_main.sites import render_site

DER = b"fake-ca" * 8
PEM = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(DER).decode() + "\n-----END CERTIFICATE-----\n"
SHA1 = hashlib.sha1(DER).hexdigest().upper()
CONTAINERS = [
    {"Name": "wp-caddy", "State": "running", "Health": ""},
    {"Name": "wp1-wordpress", "State": "running", "Health": ""},
    {"Name": "wp1-db", "State": "running", "Health": "healthy"},
    {"Name": "wp2-wordpress", "State": "running", "Health": ""},
    {"Name": "wp2-db", "State": "running", "Health": "healthy"},
]


def page(version: str) -> str:
    return f'<html><meta name="generator" content="WordPress {version}" /></html>'


class World:
    """正常な環境を表す応答。テストごとに一部を書き換えて異常を作る。"""

    def __init__(self):
        self.containers = [dict(c) for c in CONTAINERS]
        self.ps_as_array = False
        self.network = True
        self.keychain = f"SHA-1 hash: {SHA1}\n"
        self.cert_trusted = True
        self.pages = {
            "https://local.wp1.yamashita109.com/": (200, "", page("7.1.2")),
            "https://local.wp2.yamashita109.com/": (200, "", page("6.7.2")),
            "http://local.wp1.yamashita109.com/": (308, "https://local.wp1.yamashita109.com/", ""),
            "http://local.wp2.yamashita109.com/": (308, "https://local.wp2.yamashita109.com/", ""),
        }

    def respond(self, args: list[str]) -> tuple[int, str]:
        if args[:2] == ["git", "-C"]:
            site = next(s for s in SITES if args[2].endswith(s.dir_name))
            return 0, site.remote + "\n"
        if args[:3] == ["docker", "network", "inspect"]:
            return (0 if self.network else 1), ""
        if args[:3] == ["docker", "compose", "ps"]:
            if self.ps_as_array:
                return 0, json.dumps(self.containers)
            return 0, "\n".join(json.dumps(c) for c in self.containers)
        if args[:3] == ["docker", "compose", "exec"]:
            return 0, PEM
        if args[0] == "security":
            return 0, self.keychain
        if args[0] == health.CURL:
            url = args[-1]
            if not self.cert_trusted and url.startswith("https") and "-k" not in args:
                return health.CURL_SSL_ERROR, ""
            code, redirect, body = self.pages[url]
            return 0, f"{body}\n{code} {redirect}"
        raise AssertionError(f"unexpected command: {args}")


@pytest.fixture
def world():
    return World()


@pytest.fixture
def ctx_factory(tmp_path: Path, fake_runner, world):
    main = tmp_path / "wp-main"
    main.mkdir()
    (main / ".env").write_text("WP1_DOMAIN=local.wp1.yamashita109.com\n")
    for site in SITES:
        render_site(site, tmp_path / site.dir_name)
        (tmp_path / site.dir_name / ".env").write_text(
            (tmp_path / site.dir_name / ".env.example").read_text().replace("change-me", "secret")
        )

    def make(resolver=lambda domain: ["127.0.0.1"]):
        runner = fake_runner(world.respond)
        return HealthContext(runner, tmp_path, main_dir=main, resolver=resolver)

    return make


def statuses(ctx) -> dict[str, str]:
    return {o.id: o.status for o in health.run_health(ctx)}


def test_evaluate_skips_dependents_and_does_not_count_skip_as_failure():
    checks = [
        Check("a", "config", "a", lambda: Result(FAIL, "x")),
        Check("b", "config", "b", lambda: Result(OK, "y"), ("a",)),
        Check("c", "config", "c", lambda: Result(OK, "z"), ("b",)),
    ]
    outcomes = evaluate(checks)
    assert [o.status for o in outcomes] == [FAIL, SKIP, SKIP]
    assert health.summarize(outcomes) == {OK: 0, WARN: 0, FAIL: 1, SKIP: 2}


def test_evaluate_turns_exceptions_into_fail():
    def boom():
        raise RuntimeError("oops")

    [outcome] = evaluate([Check("a", "config", "a", boom)])
    assert outcome.status == FAIL and "oops" in outcome.message


def test_healthy_environment(ctx_factory):
    result = statuses(ctx_factory())
    assert set(result.values()) == {OK}
    assert len(result) == 22


def test_missing_repo_skips_env(ctx_factory, tmp_path):
    import shutil

    shutil.rmtree(tmp_path / "wp-wp1")
    result = statuses(ctx_factory())
    assert result["config.repo.wp1"] == FAIL
    assert result["config.env.wp1"] == SKIP
    assert result["container.wp1-db"] == SKIP


def test_placeholder_secret_is_warn(ctx_factory, tmp_path):
    env = tmp_path / "wp-wp2" / ".env"
    env.write_text(env.read_text().replace("MYSQL_PASSWORD=secret", "MYSQL_PASSWORD=change-me"))
    assert statuses(ctx_factory())["config.env.wp2"] == WARN


def test_dns_failure_skips_http(ctx_factory):
    result = statuses(ctx_factory(resolver=lambda domain: []))
    assert result["host.dns.wp1"] == FAIL
    assert result["http.https.wp1"] == SKIP
    assert result["http.version.wp1"] == SKIP


def test_missing_network_is_fail(ctx_factory, world):
    world.network = False
    result = statuses(ctx_factory())
    assert result["host.network"] == FAIL
    assert result["container.wp-caddy"] == SKIP


def test_untrusted_ca_is_warn_only(ctx_factory, world):
    world.keychain = ""
    world.cert_trusted = False
    outcomes = health.run_health(ctx_factory())
    result = {o.id: o.status for o in outcomes}
    assert result["host.ca"] == WARN
    assert result["http.https.wp1"] == WARN
    assert result["http.version.wp1"] == OK
    assert health.summarize(outcomes)[FAIL] == 0


@pytest.mark.parametrize("as_array", [False, True])
def test_stopped_caddy_skips_http(ctx_factory, world, as_array):
    world.ps_as_array = as_array
    world.containers[0]["State"] = "exited"
    result = statuses(ctx_factory())
    assert result["container.wp-caddy"] == FAIL
    assert result["host.ca"] == SKIP
    assert all(result[f"http.{kind}.{s.id}"] == SKIP for kind in ("https", "redirect") for s in SITES)


def test_unhealthy_db_is_fail(ctx_factory, world):
    world.containers[2]["Health"] = "starting"
    assert statuses(ctx_factory())["container.wp1-db"] == FAIL


def test_not_installed_is_fail(ctx_factory, world):
    world.pages["https://local.wp2.yamashita109.com/"] = (
        302, "https://local.wp2.yamashita109.com/wp-admin/install.php", ""
    )
    result = statuses(ctx_factory())
    assert result["http.https.wp2"] == OK
    assert result["http.installed.wp2"] == FAIL
    assert result["http.version.wp2"] == SKIP


def test_version_mismatch_is_warn(ctx_factory, world):
    world.pages["https://local.wp1.yamashita109.com/"] = (200, "", page("6.9.0"))
    assert statuses(ctx_factory())["http.version.wp1"] == WARN


def test_missing_https_redirect_is_fail(ctx_factory, world):
    world.pages["http://local.wp1.yamashita109.com/"] = (200, "", "")
    assert statuses(ctx_factory())["http.redirect.wp1"] == FAIL


def test_cli_json_and_exit_code(monkeypatch):
    outcomes = [
        health.Outcome("a", "config", "a", OK, "fine"),
        health.Outcome("b", "host", "b", FAIL, "broken", "fix it"),
    ]
    monkeypatch.setattr(health, "run_health", lambda ctx: outcomes)
    result = CliRunner().invoke(cli.app, ["dev-env:check-health", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["summary"] == {OK: 1, WARN: 0, FAIL: 1, SKIP: 0}
    assert set(payload["checks"][1]) >= {"id", "group", "status", "message", "hint"}


def test_cli_warn_only_exits_zero(monkeypatch):
    monkeypatch.setattr(health, "run_health", lambda ctx: [health.Outcome("a", "config", "a", WARN, "m", "h")])
    result = CliRunner().invoke(cli.app, ["dev-env:check-health"])
    assert result.exit_code == 0
    assert "→ h" in result.stdout


def test_help_lists_check_health():
    assert "dev-env:check-health" in CliRunner().invoke(cli.app, ["help"]).stdout
