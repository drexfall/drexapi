from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .views import auth as auth_views, database, forms, image, parser
from .views.projects import ProjectViewSet

app_name = 'core'

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = [
    path('', views.index, name='index'),

    path("api/", include(router.urls)),

    # Legacy portal CRUD
    path("read/<str:portal_name>/", database.read, name="read_database"),
    path("save/<str:portal_name>/", database.save, name="save_database"),

    path("submit/", forms.submit, name="submit"),
    path("image/upload/", image.upload, name="upload_image"),
    path("image/get/<str:image_id>/", image.get, name="get_image"),

    # Auth (Auth0-backed)
    path("auth/me/", auth_views.me, name="auth_me"),
    path("auth/sync/", auth_views.sync, name="auth_sync"),
    path("auth/password-reset/", auth_views.password_reset, name="auth_password_reset"),
    path("auth/me/delete/", auth_views.delete_me, name="auth_delete_me"),

    # Parser
    path("parser/read/", parser.read, name="parser_read"),
    path("parser/", parser.index, name="parser"),
]
