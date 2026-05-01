from django.apps import AppConfig
from .mongo import MongoConnector


class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "projects"

    def ready(self):
        MongoConnector().connect_if_needed()
