"""Standalone settings for the event-sourced / FastAPI stack.

Decoupled from Django on purpose — this layer must boot without
`DJANGO_SETTINGS_MODULE`. Reads the same env var names the Django side uses
(AUTH0_*, MONGO_*), so one `.env` drives both during the strangler migration.
"""
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", extra="ignore")

	# --- eventsourcing persistence ---
	# dev default: in-memory sqlite. prod: set PERSISTENCE_MODULE=eventsourcing.postgres
	persistence_module: str = "eventsourcing.sqlite"
	sqlite_dbname: str = ":memory:"
	postgres_dbname: str = ""
	postgres_host: str = "localhost"
	postgres_port: str = "5432"
	postgres_user: str = ""
	postgres_password: str = ""

	# --- Auth0 (mirrors Django settings) ---
	auth0_domain: str = ""
	auth0_audience: str = ""
	auth0_claims_namespace: str = "https://drexapi/"
	auth0_client_id: str = ""
	auth0_mgmt_client_id: str = ""
	auth0_mgmt_client_secret: str = ""

	# --- carousel ingest (shared-secret machine channel) ---
	carousel_ingest_token: str = ""

	# --- carousel render/storage/publish adapters ---
	# real render = WeasyPrint+pypdfium (needs system libs); off by default so dev
	# uses the placeholder LocalRenderer.
	carousel_real_render: bool = False
	imagekit_private: str = ""
	imagekit_public: str = ""
	imagekit_url_endpoint: str = ""
	media_root: str = "media"
	media_url: str = "/media/"
	# Meta Graph API (Instagram publish)
	meta_ig_user_id: str = ""
	meta_access_token: str = ""
	meta_graph_version: str = "v23.0"

	# --- Celery (async carousel render at scale) ---
	celery_broker_url: str = "redis://localhost:6379/0"
	celery_result_backend: str = "redis://localhost:6379/0"

	# --- Mongo read models ---
	# accepts either MONGO_URI (Django side) or MONGODB_URI (existing .env)
	mongo_uri: str = Field(
		default="", validation_alias=AliasChoices("MONGO_URI", "MONGODB_URI")
	)
	mongo_db: str = "drexapi_projects"

	def es_env(self) -> dict[str, str]:
		"""Translate settings into the env dict eventsourcing.Application expects."""
		env: dict[str, str] = {"PERSISTENCE_MODULE": self.persistence_module}
		if self.persistence_module.endswith("sqlite"):
			env["SQLITE_DBNAME"] = self.sqlite_dbname
		elif self.persistence_module.endswith("postgres"):
			env.update(
				{
					"POSTGRES_DBNAME": self.postgres_dbname,
					"POSTGRES_HOST": self.postgres_host,
					"POSTGRES_PORT": self.postgres_port,
					"POSTGRES_USER": self.postgres_user,
					"POSTGRES_PASSWORD": self.postgres_password,
				}
			)
		return env


@lru_cache
def get_settings() -> Settings:
	return Settings()
