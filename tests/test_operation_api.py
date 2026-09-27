import json
from datetime import datetime, timedelta, timezone

import pytest
from django.test import Client

from wp_main.dashboard import models
from wp_main.dashboard.models import Operation

TOKEN = "test-token"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def api_token(monkeypatch):
    monkeypatch.setenv("DASHBOARD_API_TOKEN", TOKEN)


def payload(**values):
    finished = datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc)
    return {
        "command": "migrate",
        "options": {"auto": True},
        "started_at": (finished - timedelta(seconds=30)).isoformat(),
        "finished_at": finished.isoformat(),
        "exit_code": 0,
        "succeeded": True,
        "summary": "3 → 4",
    } | values


def post(client, body, **headers):
    return client.post("/api/operations", json.dumps(body), content_type="application/json", **headers)


@pytest.mark.django_db
def test_record_operation():
    response = post(Client(), payload(), **AUTH)
    assert response.status_code == 201
    assert response.json()["summary"] == "3 → 4"
    assert Operation.objects.get().options == {"auto": True}


@pytest.mark.django_db
@pytest.mark.parametrize("headers", [{}, {"HTTP_AUTHORIZATION": "Bearer wrong"}])
def test_rejects_missing_or_wrong_token(headers):
    assert post(Client(), payload(), **headers).status_code == 401
    assert Operation.objects.count() == 0


@pytest.mark.django_db
def test_rejects_everything_without_configured_token(monkeypatch):
    monkeypatch.setenv("DASHBOARD_API_TOKEN", "")
    assert post(Client(), payload(), HTTP_AUTHORIZATION="Bearer ").status_code == 401
    assert Client().get("/api/operations", HTTP_AUTHORIZATION="Bearer anything").status_code == 401
    assert Operation.objects.count() == 0


@pytest.mark.django_db
def test_rejects_unknown_command():
    assert post(Client(), payload(command="uninstall"), **AUTH).status_code == 422


@pytest.mark.django_db
def test_truncates_summary():
    post(Client(), payload(summary="x" * 600), **AUTH)
    assert len(Operation.objects.get().summary) == 500


@pytest.mark.django_db
def test_list_newest_first_with_limit():
    client = Client()
    for minute in range(3):
        finished = datetime(2026, 9, 27, 10, minute, tzinfo=timezone.utc).isoformat()
        post(client, payload(finished_at=finished, summary=str(minute)), **AUTH)
    response = client.get("/api/operations?limit=2", **AUTH)
    assert response.status_code == 200
    assert [item["summary"] for item in response.json()] == ["2", "1"]


@pytest.mark.django_db
@pytest.mark.parametrize("limit", [0, 101])
def test_list_limit_range(limit):
    assert Client().get(f"/api/operations?limit={limit}", **AUTH).status_code == 422


@pytest.mark.django_db
def test_prunes_beyond_limit(monkeypatch):
    monkeypatch.setattr(models, "MAX_OPERATIONS", 2)
    client = Client()
    for minute in range(3):
        finished = datetime(2026, 9, 27, 10, minute, tzinfo=timezone.utc).isoformat()
        post(client, payload(finished_at=finished, summary=str(minute)), **AUTH)
    assert [op.summary for op in Operation.objects.all()] == ["2", "1"]
