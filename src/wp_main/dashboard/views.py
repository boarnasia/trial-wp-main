from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe
from ninja import NinjaAPI

from .. import operations, power
from ..config import SITES
from ..runner import DevEnvError, Runner
from .data import find_password, load_sites, sites_root
from .models import Operation

ACTIONS = {"start": (power.start, "起動"), "stop": (power.stop, "停止")}

NO_STORE = {"Cache-Control": "no-store"}
# FastAPI 版と同じく日本語をエスケープせずに返す
UTF8 = {"ensure_ascii": False}

api = NinjaAPI(title="wp-main dashboard", docs_url=None, openapi_url=None)
RECENT_OPERATIONS = 20


# curl -I などの HEAD による疎通確認で 405 にならないようにする
@require_safe
def index(request):
    runner, root = Runner(), sites_root()
    rows = []
    for view, site in zip(load_sites(root), SITES):
        state = power.inspect(runner, site)
        busy = power.is_busy(site)
        rows.append((view, {
            "state": state,
            "busy": busy,
            "disabled": busy or state.state == power.UNKNOWN,
            "action": "start" if state.state == power.STOPPED else "stop",
        }))
    context = {
        "rows": rows,
        "sites": [view for view, _ in rows],
        "operations": Operation.objects.all()[:RECENT_OPERATIONS],
    }
    return TemplateResponse(request, "index.html", context, headers=NO_STORE)


@api.get("/sites/{site_id}/password")
def password(request, site_id: str):
    value = find_password(site_id)
    if value is None:
        return JsonResponse({"detail": "パスワードが見つかりません"}, status=404, headers=NO_STORE, json_dumps_params=UTF8)
    return JsonResponse({"password": value}, headers=NO_STORE, json_dumps_params=UTF8)


@require_POST
def site_action(request, site_id: str, action: str):
    site = next((site for site in SITES if site.id == site_id), None)
    if site is None or action not in ACTIONS:
        raise Http404
    run, label = ACTIONS[action]
    started = timezone.now()
    try:
        with power.site_lock(site):
            run(Runner(), site, sites_root())
    except power.Busy:
        messages.warning(request, f"{site.id} は別の操作を実行中です。終わってからやり直してください")
        return redirect("/")
    except DevEnvError as error:
        summary = f"{site.id} の{label}に失敗しました: {error}"
        operations.record(f"site-{action}", {"site": site.id, "via": "dashboard"}, started, timezone.now(),
                          exit_code=1, succeeded=False, summary=summary)
        messages.error(request, summary)
        return redirect("/")
    summary = f"{site.id} を{label}しました"
    operations.record(f"site-{action}", {"site": site.id, "via": "dashboard"}, started, timezone.now(),
                      exit_code=0, succeeded=True, summary=summary)
    messages.success(request, summary)
    return redirect("/")


@require_safe
def healthz(request):
    return JsonResponse({"status": "ok"})
