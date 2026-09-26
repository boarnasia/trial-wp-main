import pytest

from wp_main.docker import check_ports
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
