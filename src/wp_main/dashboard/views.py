import hmac
import os
from datetime import datetime
from typing import Literal

from django.db import transaction
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe
from ninja import Field, NinjaAPI, Query, Schema, Status
from ninja.security import HttpBearer

from .data import find_password, load_sites
from .models import Operation

NO_STORE = {"Cache-Control": "no-store"}
# FastAPI 版と同じく日本語をエスケープせずに返す
UTF8 = {"ensure_ascii": False}

api = NinjaAPI(title="wp-main dashboard", docs_url=None, openapi_url=None)
SUMMARY_LIMIT = Operation._meta.get_field("summary").max_length
RECENT_OPERATIONS = 20


class TokenAuth(HttpBearer):
    def authenticate(self, request, token: str) -> bool:
        expected = os.environ.get("DASHBOARD_API_TOKEN", "")
        # トークンが未設定のときに空文字列の一致で通してしまわないようにする
        return bool(expected) and hmac.compare_digest(token.encode(), expected.encode())


class OperationIn(Schema):
    command: Literal["install", "migrate", "check-health"]
    options: dict = {}
    started_at: datetime
    finished_at: datetime
    exit_code: int
    succeeded: bool
    summary: str


class OperationOut(OperationIn):
    id: int
    command: str


class ListParams(Schema):
    limit: int = Field(20, ge=1, le=100)


# curl -I などの HEAD による疎通確認で 405 にならないようにする
@require_safe
def index(request):
    context = {"sites": load_sites(), "operations": Operation.objects.all()[:RECENT_OPERATIONS]}
    return TemplateResponse(request, "index.html", context, headers=NO_STORE)


@api.get("/sites/{site_id}/password")
def password(request, site_id: str):
    value = find_password(site_id)
    if value is None:
        return JsonResponse({"detail": "パスワードが見つかりません"}, status=404, headers=NO_STORE, json_dumps_params=UTF8)
    return JsonResponse({"password": value}, headers=NO_STORE, json_dumps_params=UTF8)


@api.post("/operations", auth=TokenAuth(), response={201: OperationOut})
def record_operation(request, payload: OperationIn):
    values = payload.dict()
    values["summary"] = values["summary"][:SUMMARY_LIMIT]
    with transaction.atomic():
        operation = Operation.objects.create(**values)
        Operation.prune()
    return Status(201, operation)


@api.get("/operations", auth=TokenAuth(), response=list[OperationOut])
def list_operations(request, params: Query[ListParams]):
    return Operation.objects.all()[: params.limit]


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})
