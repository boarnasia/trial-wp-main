from django.contrib import messages
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe
from ninja import NinjaAPI

from .. import operations, plugins, power, session, versioning
from ..config import MYSQL_IMAGE, SITES
from ..runner import DevEnvError, Runner
from ..sites import proxy_is_public
from . import plugin_list as plugin_list_data
from .data import find_db_password, find_password, load_db, load_sites, main_dir, sites_root
from .models import Operation

ACTIONS = {"start": (power.start, "起動"), "stop": (power.stop, "停止")}
SHUTDOWN_FORBIDDEN = "プロキシを LAN に公開している（PROXY_BIND_ADDRESS）ため、ダッシュボードから開発セッションは終了できません"

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
    context = header_context("dashboard", root) | {
        "rows": rows,
        "db": load_db(),
        "mysql": power.inspect_mysql(runner),
        "mysql_version": "MySQL " + MYSQL_IMAGE.rpartition(":")[2],
        "operations": Operation.objects.all()[:RECENT_OPERATIONS],
    }
    return TemplateResponse(request, "index.html", context, headers=NO_STORE)


def header_context(section: str, root) -> dict:
    installed, latest = versioning.installed_version(root), versioning.latest()
    return {
        "section": section,
        "sites": SITES,
        "env_version": installed,
        "env_outdated": installed is not None and installed < latest,
        "env_latest": latest,
        "can_shutdown": not proxy_is_public(main_dir()),
    }


@require_safe
def plugin_list(request):
    root = sites_root()
    context = header_context("wordpress", root) | {"table": plugin_list_data.build_table(base=root)}
    return TemplateResponse(request, "plugins.html", context, headers=NO_STORE)


@require_POST
def plugin_refresh(request):
    started = timezone.now()
    try:
        with plugins.refresh_lock():
            result = plugin_list_data.refresh(Runner())
    except plugins.Busy:
        messages.warning(request, "プラグイン情報は別の再取得で取得中です。終わってから再読み込みしてください")
        return redirect("/wordpress/plugins")
    operations.record("plugins-refresh", {"via": "dashboard"}, started, timezone.now(),
                      exit_code=0 if result.succeeded else 1, succeeded=result.succeeded, summary=result.summary)
    notify = messages.success if result.succeeded else messages.warning
    notify(request, f"プラグイン情報を再取得しました: {result.summary}")
    return redirect("/wordpress/plugins")


@api.get("/sites/{site_id}/password")
def password(request, site_id: str):
    value = find_password(site_id)
    if value is None:
        return JsonResponse({"detail": "パスワードが見つかりません"}, status=404, headers=NO_STORE, json_dumps_params=UTF8)
    return JsonResponse({"password": value}, headers=NO_STORE, json_dumps_params=UTF8)


@api.get("/db/{account}/password")
def db_password(request, account: str):
    value = find_db_password(account)
    if value is None:
        return JsonResponse({"detail": "パスワードが見つかりません"}, status=404, headers=NO_STORE, json_dumps_params=UTF8)
    return JsonResponse({"password": value}, headers=NO_STORE, json_dumps_params=UTF8)


@require_POST
def shutdown(request):
    if proxy_is_public(main_dir()):
        return HttpResponseForbidden(SHUTDOWN_FORBIDDEN)
    session.spawn_down(sites_root())
    return JsonResponse({"status": "stopping"}, status=202, json_dumps_params=UTF8)


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
