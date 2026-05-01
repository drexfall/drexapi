import os

from celery import Celery
from celery.schedules import schedule

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drexfall.settings")

app = Celery("drexfall")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
	"drain-outbox": {
		"task": "projects.drain_outbox",
		"schedule": schedule(run_every=1.0),
	},
}
