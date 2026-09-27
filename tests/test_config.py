from pathlib import Path

import pytest

from wp_main.config import DEFAULT_DASHBOARD_PORT, MAIN_DIR, SITES, resolve_root
from wp_main.runner import DevEnvError
from wp_main.sites import dashboard_port, proxy_is_public


def test_default_root_is_parent_of_wp_main():
    assert resolve_root(None) == MAIN_DIR.parent


def test_explicit_root(tmp_path: Path):
    assert resolve_root(tmp_path) == tmp_path.resolve()


def test_site_names_are_prefixed():
    for site in SITES:
        assert site.wordpress_service.startswith(site.id)
        assert all(volume.startswith(site.id) for volume in site.volumes)


def test_dashboard_port_default(tmp_path: Path):
    assert dashboard_port(tmp_path) == DEFAULT_DASHBOARD_PORT


def test_dashboard_port_from_env(tmp_path: Path):
    (tmp_path / ".env").write_text("DASHBOARD_PORT=8123\n")
    assert dashboard_port(tmp_path) == 8123


def test_dashboard_port_invalid(tmp_path: Path):
    (tmp_path / ".env").write_text("DASHBOARD_PORT=abc\n")
    with pytest.raises(DevEnvError):
        dashboard_port(tmp_path)


@pytest.mark.parametrize(("line", "public"), [("", False), ("PROXY_BIND_ADDRESS=127.0.0.1\n", False),
                                                ("PROXY_BIND_ADDRESS=0.0.0.0\n", True)])
def test_proxy_is_public(tmp_path: Path, line: str, public: bool):
    (tmp_path / ".env").write_text(line)
    assert proxy_is_public(tmp_path) is public
