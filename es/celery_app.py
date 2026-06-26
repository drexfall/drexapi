"""Standalone Celery app (replaces drexfall/celery.py — no Django).

Configured from es.config.Settings. Today carousel render runs via FastAPI
BackgroundTasks; this app is the home for that work when moved to a real
worker. Example task included.

Run a worker:  celery -A es.celery_app:app worker -l info
"""
from celery import Celery

from es.config import get_settings

_settings = get_settings()
app = Celery("drexapi", broker=_settings.celery_broker_url, backend=_settings.celery_result_backend)
app.conf.update(task_serializer="json", accept_content=["json"], timezone="UTC")


@app.task(name="carousels.render")
def render_carousel(carousel_id: str) -> None:
	from uuid import UUID

	from es.carousels.adapters import default_renderer
	from es.carousels.pipeline import run_render
	from es.carousels.system import get_carousels_app

	run_render(get_carousels_app(), UUID(carousel_id), default_renderer())
