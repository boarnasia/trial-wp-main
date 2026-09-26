from django.urls import include, path

urlpatterns = [path("", include("wp_main.dashboard.urls"))]
