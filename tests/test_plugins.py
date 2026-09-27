import io
import json
import urllib.error

import pytest

from wp_main import plugins
from wp_main.config import SITES

WP1, WP2 = SITES


@pytest.mark.parametrize(("major", "requires", "tested", "status"), [
    (6, "6.3", "7.0.6", plugins.OK),
    (7, "6.3", "7.0.6", plugins.OK),
    (5, "6.3", "7.0.6", plugins.NG),
    (8, "6.3", "7.0.6", plugins.NG),
    (6, "", "7.0", plugins.UNKNOWN),
    (6, "6.3", "", plugins.UNKNOWN),
])
def test_major_status(major, requires, tested, status):
    assert plugins.major_status(major, requires, tested) == status


@pytest.mark.parametrize(("version", "requires", "tested", "supported"), [
    ("6.7", "6.3", "6.8", True),
    ("6.8.1", "6.3", "6.8", True),  # 同じマイナー版なら動作確認済みとみなす
    ("6.7.2", "6.8", "7.0", False),
    ("7.1", "6.3", "7.0.6", False),
    ("6.7", "", "6.8", None),
])
def test_site_supported(version, requires, tested, supported):
    assert plugins.site_supported(version, requires, tested) is supported


class CliRunner:
    """docker compose run の wp コマンドだけを受け、あらかじめ決めた結果を返す。"""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def run(self, args, *, cwd=None, check=True, capture=False, mutate=True, env=None):
        import subprocess

        self.calls.append(list(args))
        wp_args = tuple(args[args.index("wp") + 1:])
        code, out, err = self.responses[wp_args[:2]]
        return subprocess.CompletedProcess(args, code, out, err)


LISTED = json.dumps([
    {"name": "query-monitor", "title": "Query Monitor", "version": "3.17.2", "status": "active"},
    {"name": "classic-editor", "title": "Classic Editor", "version": "1.6.7", "status": "inactive"},
    {"name": "loader", "title": "Loader &amp; Co", "version": "", "status": "must-use"},
    {"name": "object-cache.php", "title": "Redis", "version": "2.0", "status": "dropin"},
])


def test_fetch_site_uses_cli_without_starting(tmp_path):
    runner = CliRunner({("core", "version"): (0, "6.7.2\n", ""), ("plugin", "list"): (0, LISTED, "")})
    result = plugins.fetch_site(runner, WP2, main_dir=tmp_path)
    assert result.error is None and result.wp_version == "6.7.2"
    assert [item.slug for item in result.plugins] == ["query-monitor", "classic-editor", "loader"]
    assert result.plugins[2].title == "Loader & Co"
    for call in runner.calls:
        assert call[:5] == ["docker", "compose", "run", "--rm", "-T"] and "wp2-cli" in call
    assert not any("up" in call or "start" in call for call in runner.calls)


def test_fetch_site_without_wordpress_files(tmp_path):
    runner = CliRunner({("core", "version"): (1, "", "Error: This does not seem to be a WordPress installation.")})
    result = plugins.fetch_site(runner, WP1, main_dir=tmp_path)
    assert result.error == plugins.NOT_INSTALLED_HINT


def test_fetch_site_bad_json(tmp_path):
    runner = CliRunner({("core", "version"): (0, "7.1\n", ""), ("plugin", "list"): (0, "PHP Warning", "")})
    assert "wp plugin list が失敗しました" in plugins.fetch_site(runner, WP1, main_dir=tmp_path).error


def fake_urlopen(payload=None, error=None):
    def urlopen(url, timeout):
        if error:
            raise error
        return io.BytesIO(json.dumps(payload).encode())

    return urlopen


def test_fetch_org_found(monkeypatch):
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen(
        {"name": "Query &amp; Monitor", "requires": "6.2", "tested": "7.0.6"}))
    assert plugins.fetch_org("query-monitor") == plugins.OrgInfo(True, "Query & Monitor", "6.2", "7.0.6")


def test_fetch_org_not_found(monkeypatch):
    error = urllib.error.HTTPError("u", 404, "Not Found", {}, io.BytesIO(b'{"error":"Plugin not found."}'))
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen(error=error))
    assert plugins.fetch_org("in-house") == plugins.OrgInfo(found=False)


def test_fetch_org_unreachable(monkeypatch):
    monkeypatch.setattr(plugins.urllib.request, "urlopen", fake_urlopen(error=urllib.error.URLError("offline")))
    assert plugins.fetch_org("query-monitor") is None


def test_refresh_lock_rejects_second(tmp_path):
    with plugins.refresh_lock(tmp_path):
        with pytest.raises(plugins.Busy):
            with plugins.refresh_lock(tmp_path):
                pass
