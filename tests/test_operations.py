import json
import urllib.error
from datetime import datetime, timezone

import pytest

from wp_main import operations
from wp_main.operations import send as real_send

START = datetime(2026, 9, 27, 1, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 27, 1, 1, tzinfo=timezone.utc)


def call(sender, **values):
    fields = {"exit_code": 0, "succeeded": True, "summary": "3 → 4"} | values
    return operations.record("migrate", {"auto": True, "root": None}, START, END, sender=sender, **fields)


def test_record_sends_payload():
    sent = []
    assert call(sent.append)
    assert sent == [{
        "command": "migrate", "options": {"auto": True, "root": None},
        "started_at": START.isoformat(), "finished_at": END.isoformat(),
        "exit_code": 0, "succeeded": True, "summary": "3 → 4",
    }]


def test_record_failure_only_warns(capsys):
    def down(payload):
        raise operations.ApiError("Connection refused")

    assert call(down) is False
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "操作履歴を記録できませんでした: Connection refused" in captured.err


def test_missing_token_is_rejected(tmp_path):
    (tmp_path / ".env").write_text("DASHBOARD_API_TOKEN=change-me\n")
    with pytest.raises(operations.ApiError, match="DASHBOARD_API_TOKEN"):
        operations.api_token(tmp_path)


def test_send_posts_with_token(monkeypatch, tmp_path):
    captured = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout, context):
        captured.update(url=request.full_url, auth=request.get_header("Authorization"), body=json.loads(request.data), timeout=timeout)
        return Response()

    monkeypatch.setattr(operations, "api_token", lambda: "secret")
    monkeypatch.setattr(operations, "ca_file", lambda runner: tmp_path / "ca.crt")
    monkeypatch.setattr(operations.ssl, "create_default_context", lambda cafile: None)
    monkeypatch.setattr(operations.urllib.request, "urlopen", fake_urlopen)
    real_send({"command": "migrate"})
    assert captured == {"url": operations.API_URL, "auth": "Bearer secret", "body": {"command": "migrate"}, "timeout": 3}


def test_send_unreachable_raises(monkeypatch, tmp_path):
    def refused(request, timeout, context):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(operations, "api_token", lambda: "secret")
    monkeypatch.setattr(operations, "ca_file", lambda runner: tmp_path / "ca.crt")
    monkeypatch.setattr(operations.ssl, "create_default_context", lambda cafile: None)
    monkeypatch.setattr(operations.urllib.request, "urlopen", refused)
    with pytest.raises(operations.ApiError, match="Connection refused"):
        real_send({})
