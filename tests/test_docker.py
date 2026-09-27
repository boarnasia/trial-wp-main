import pytest

from wp_main.docker import check_ports, compose
from wp_main.runner import DevEnvError


def test_busy_port_raises(fake_runner):
    runner = fake_runner(lambda args: (0, "caddy 123 LISTEN" if args[0] == "lsof" else ""))
    with pytest.raises(DevEnvError, match="80"):
        check_ports(runner, (80, 443), is_free=lambda port: port != 80)


def test_free_ports_pass(fake_runner):
    check_ports(fake_runner(), (80, 443), is_free=lambda port: True)


def test_skips_when_own_caddy_running(fake_runner):
    runner = fake_runner(lambda args: (0, "abc123" if "ps" in args else ""))
    check_ports(runner, (80,), is_free=lambda port: False)


def test_compose_points_missing_site_env_to_dev_null(tmp_path, fake_runner):
    main_dir = tmp_path / "wp-main"
    main_dir.mkdir()
    (tmp_path / "wp-wp1").mkdir()
    (tmp_path / "wp-wp1" / ".env").write_text("")
    runner = fake_runner()
    compose(runner, "ps", cwd=main_dir)
    assert runner.envs == [{"WP2_ENV_FILE": "/dev/null"}]
