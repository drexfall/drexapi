from django.contrib import admin
from django.urls import path, include, re_path

from core.views import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("scan/", include("scan.urls")),
    path("profiles/", include("profiles.urls")),
    # SPA catch-all — must be last
    re_path(r"^(?!static/|media/).*$", spa),
]
