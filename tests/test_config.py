from pathlib import Path

from wp_main.config import MAIN_DIR, SITES, resolve_root


def test_default_root_is_parent_of_wp_main():
    assert resolve_root(None) == MAIN_DIR.parent


def test_explicit_root(tmp_path: Path):
    assert resolve_root(tmp_path) == tmp_path.resolve()


def test_site_names_are_prefixed():
    for site in SITES:
        assert site.wordpress_service.startswith(site.id)
        assert all(volume.startswith(site.id) for volume in site.volumes)
