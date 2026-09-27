from datetime import timedelta

import pytest
from django.utils import timezone

from wp_main.dashboard.models import Operation


def make(minutes: int, **values) -> Operation:
    now = timezone.now()
    fields = {
        "command": "migrate",
        "options": {"auto": True},
        "started_at": now + timedelta(minutes=minutes - 1),
        "finished_at": now + timedelta(minutes=minutes),
        "exit_code": 0,
        "succeeded": True,
        "summary": "3 → 4",
    } | values
    return Operation.objects.create(**fields)


@pytest.mark.django_db
def test_save_and_read_newest_first():
    make(0, summary="old")
    make(5, summary="new", command="check-health", options={})
    assert [op.summary for op in Operation.objects.all()] == ["new", "old"]
    assert Operation.objects.first().options == {}


@pytest.mark.django_db
def test_prune_keeps_newest():
    for minutes in range(5):
        make(minutes, summary=str(minutes))
    assert Operation.prune(keep=3) == 2
    assert [op.summary for op in Operation.objects.all()] == ["4", "3", "2"]
