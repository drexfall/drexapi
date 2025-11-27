from django.urls import path

from . import views

app_name = 'scan'
urlpatterns = [
	path('', views.index, name='index'),
	path('<str:code_id>', views.index, name='index'),
]
