from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView

from .views import api, healthz, index, shutdown, site_action

urlpatterns = [
    path("", index),
    path("api/", api.urls),
    path("sites/<str:site_id>/<str:action>", site_action),
    path("session/shutdown", shutdown),
    path("healthz", healthz),
    # link 要素を読まずに /favicon.ico を直接取りに来るクライアント向け
    path("favicon.ico", RedirectView.as_view(url=static("favicon.svg"), permanent=True)),
]
