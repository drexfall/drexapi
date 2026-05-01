import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Project(models.Model):
	class Status(models.TextChoices):
		PROVISIONING = "provisioning", "Provisioning"
		READY = "ready", "Ready"
		DELETING = "deleting", "Deleting"
		FAILED = "failed", "Failed"

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	slug = models.SlugField(max_length=60, unique=True)
	name = models.CharField(max_length=120)
	description = models.TextField(blank=True, default="")
	owner = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name="owned_projects",
	)
	status = models.CharField(
		max_length=16,
		choices=Status.choices,
		default=Status.PROVISIONING,
	)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(default=timezone.now)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [models.Index(fields=["owner", "created_at"])]

	def __str__(self):
		return f"{self.name} ({self.slug})"

	@property
	def mongo_collection(self) -> str:
		return f"project_{self.id.hex}"


class Outbox(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		PROCESSING = "processing", "Processing"
		PROCESSED = "processed", "Processed"
		FAILED = "failed", "Failed"

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	event_type = models.CharField(max_length=64, db_index=True)
	aggregate_id = models.CharField(max_length=64, db_index=True)
	payload = models.JSONField(default=dict)
	status = models.CharField(
		max_length=16,
		choices=Status.choices,
		default=Status.PENDING,
		db_index=True,
	)
	attempts = models.PositiveIntegerField(default=0)
	last_error = models.TextField(blank=True, default="")
	available_at = models.DateTimeField(default=timezone.now, db_index=True)
	created_at = models.DateTimeField(default=timezone.now)
	processed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		indexes = [models.Index(fields=["status", "available_at"])]
		ordering = ["created_at"]
