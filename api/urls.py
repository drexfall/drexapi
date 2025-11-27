from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from .views import auth as auth_views, database, forms, image, parser

urlpatterns = [
	path("read/<str:portal_name>/", database.read, name="read_database"),
	path("save/<str:portal_name>/", database.save, name="save_database"),

	path("submit/", forms.submit, name="index"),
	path("image/upload/", image.upload, name="upload_image"),
	path("image/get/<str:image_id>/", image.get, name="get_image"),
	# path("form/<str:portal_name>/<str:form_name>", views.form, name="form"),
	# Authentication
	path("auth/token/", auth_views.MyTokenObtainPairView.as_view(), name="get_token"),
	path("auth/token/refresh", jwt_views.TokenRefreshView.as_view(), name="refresh_token"),
	path('auth/register/', auth_views.RegisterView.as_view(), name='auth_register'),

	# Profiles
	path('profile/', auth_views.get_profile, name='profile'),
	path('profile/update/', auth_views.update_profile, name='update_profile'),

	# Parser
	path('parser/read/', parser.read, name='parser_read'),
	path('parser/', parser.index, name='parser'),
]
