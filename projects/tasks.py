import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Outbox, Project
from .mongo import drop_project_collection, ensure_project_collection, project_collection

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BATCH_SIZE = 50


@shared_task(name="projects.drain_outbox")
def drain_outbox() -> dict:
	"""Claim pending rows, dispatch, mark processed. Idempotent per row."""
	now = timezone.now()
	processed = 0
	failed = 0

	with transaction.atomic():
		ids = list(
			Outbox.objects.select_for_update(skip_locked=True)
			.filter(status=Outbox.Status.PENDING, available_at__lte=now)
			.order_by("created_at")
			.values_list("id", flat=True)[:BATCH_SIZE]
		)
		if ids:
			Outbox.objects.filter(id__in=ids).update(status=Outbox.Status.PROCESSING)

	for row_id in ids:
		row = Outbox.objects.get(pk=row_id)
		try:
			_dispatch(row)
			row.status = Outbox.Status.PROCESSED
			row.processed_at = timezone.now()
			row.save(update_fields=["status", "processed_at"])
			processed += 1
		except Exception as exc:
			row.attempts += 1
			row.last_error = str(exc)[:2000]
			if row.attempts >= MAX_ATTEMPTS:
				row.status = Outbox.Status.FAILED
			else:
				row.status = Outbox.Status.PENDING
				row.available_at = timezone.now() + timedelta(seconds=2 ** row.attempts)
			row.save(update_fields=["status", "attempts", "last_error", "available_at"])
			failed += 1
			logger.exception("outbox dispatch failed id=%s", row_id)

	return {"processed": processed, "failed": failed}


def _dispatch(row: Outbox) -> None:
	handler = _HANDLERS.get(row.event_type)
	if handler is None:
		raise RuntimeError(f"no handler for {row.event_type}")
	handler(row.payload)


def _on_project_created(payload: dict) -> None:
	project_id = payload["id"]
	try:
		project = Project.objects.get(pk=project_id)
	except Project.DoesNotExist:
		return
	ensure_project_collection(project.id)
	coll = project_collection(project.id)
	coll.update_one(
		{"doc_type": "read_model"},
		{
			"$set": {
				"doc_type": "read_model",
				"id": str(project.id),
				"slug": project.slug,
				"name": project.name,
				"description": project.description,
				"owner_id": project.owner_id,
				"metadata": project.metadata,
				"status": Project.Status.READY,
				"created_at": project.created_at,
				"updated_at": project.updated_at,
			}
		},
		upsert=True,
	)
	Project.objects.filter(pk=project.id).update(status=Project.Status.READY)


def _on_project_updated(payload: dict) -> None:
	project_id = payload["id"]
	try:
		project = Project.objects.get(pk=project_id)
	except Project.DoesNotExist:
		return
	coll = project_collection(project.id)
	coll.update_one(
		{"doc_type": "read_model"},
		{
			"$set": {
				"name": project.name,
				"description": project.description,
				"metadata": project.metadata,
				"updated_at": project.updated_at,
			}
		},
		upsert=True,
	)


def _on_project_deleted(payload: dict) -> None:
	import uuid
	drop_project_collection(uuid.UUID(payload["id"]))


def _on_member_changed(payload: dict) -> None:
	# Placeholder — read model could embed member list; skip for v1.
	return


_HANDLERS = {
	"project.created": _on_project_created,
	"project.updated": _on_project_updated,
	"project.deleted": _on_project_deleted,
	"project.member_added": _on_member_changed,
	"project.member_removed": _on_member_changed,
}
