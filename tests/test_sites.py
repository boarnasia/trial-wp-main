import subprocess
from pathlib import Path

import pytest

from wp_main.config import SITES
from wp_main.runner import DevEnvError
from wp_main.sites import (
    SECRET_PLACEHOLDER, ensure_env, ensure_site_repo, parse_env, render_site, render_text,
)

WP1 = SITES[0]


def test_render_unknown_placeholder():
    with pytest.raises(DevEnvError):
        render_text("{{NOPE}}", {})


def test_render_site_leaves_compose_variables(tmp_path: Path):
    render_site(WP1, tmp_path)
    compose = (tmp_path / "docker-compose.yml").read_text()
    assert "wp1-wordpress:" in compose and "{{" not in compose
    assert "${MYSQL_PASSWORD}" in compose
    env = parse_env((tmp_path / ".env.example").read_text())
    assert env["WP_IMAGE"] == "wordpress:7.1-apache"
    assert env["WP_HOME"] == "https://local.wp1.yamashita109.com"


def test_existing_clone_is_skipped(tmp_path: Path, fake_runner):
    (tmp_path / "wp-wp1" / ".git").mkdir(parents=True)
    runner = fake_runner(lambda args: (0, WP1.remote + "\n"))
    assert ensure_site_repo(runner, WP1, tmp_path) == "exists"
    assert not runner.mutating(["git", "clone"])


def test_unrelated_directory_is_error(tmp_path: Path, fake_runner):
    (tmp_path / "wp-wp1" / "wp-site2").mkdir(parents=True)
    runner = fake_runner()
    with pytest.raises(DevEnvError, match="wp-wp1"):
        ensure_site_repo(runner, WP1, tmp_path)
    assert runner.calls == []


def test_empty_remote_is_scaffolded(tmp_path: Path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    site = WP1.__class__(**{**WP1.__dict__, "remote": str(remote)})
    (tmp_path / "wp-wp1").mkdir()  # 空ディレクトリは clone 先として扱う

    from wp_main.runner import Runner
    assert ensure_site_repo(Runner(), site, tmp_path) == "scaffolded"
    repo = tmp_path / "wp-wp1"
    assert (repo / "config" / "wp-config-proxy.php").exists()
    log = subprocess.run(["git", "-C", str(repo), "log", "--oneline"], capture_output=True, text=True)
    assert len(log.stdout.splitlines()) == 1
    pushed = subprocess.run(["git", "-C", str(remote), "log", "--oneline"], capture_output=True, text=True)
    assert pushed.returncode != 0  # push していない


def test_env_generated_with_secrets(tmp_path: Path, fake_runner):
    render_site(WP1, tmp_path)
    assert ensure_env(fake_runner(), tmp_path)
    env = parse_env((tmp_path / ".env").read_text())
    assert env["MYSQL_PASSWORD"] != SECRET_PLACEHOLDER
    assert env["MYSQL_PASSWORD"] != env["MYSQL_ROOT_PASSWORD"]
    assert env["MYSQL_USER"] == "wordpress"


def test_env_not_overwritten(tmp_path: Path, fake_runner):
    render_site(WP1, tmp_path)
    (tmp_path / ".env").write_text("KEEP=1\n")
    assert not ensure_env(fake_runner(), tmp_path)
    assert (tmp_path / ".env").read_text() == "KEEP=1\n"
