from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe
from ninja import NinjaAPI

from .data import find_password, load_sites

NO_STORE = {"Cache-Control": "no-store"}
# FastAPI 版と同じく日本語をエスケープせずに返す
UTF8 = {"ensure_ascii": False}

api = NinjaAPI(title="wp-main dashboard", docs_url=None, openapi_url=None)


# curl -I などの HEAD による疎通確認で 405 にならないようにする
@require_safe
def index(request):
    return TemplateResponse(request, "index.html", {"sites": load_sites()}, headers=NO_STORE)


@api.get("/sites/{site_id}/password")
def password(request, site_id: str):
    value = find_password(site_id)
    if value is None:
        return JsonResponse({"detail": "パスワードが見つかりません"}, status=404, headers=NO_STORE, json_dumps_params=UTF8)
    return JsonResponse({"password": value}, headers=NO_STORE, json_dumps_params=UTF8)


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})
