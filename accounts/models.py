import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	external_id = models.CharField(max_length=255, unique=True, db_index=True)
	email_verified = models.BooleanField(default=False)
	created_at = models.DateTimeField(default=timezone.now)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.user.username} ({self.external_id})"


class Role(models.TextChoices):
	VIEWER = "viewer", "Viewer"
	EDITOR = "editor", "Editor"
	ADMIN = "admin", "Admin"


ROLE_RANK = {Role.VIEWER: 1, Role.EDITOR: 2, Role.ADMIN: 3}


class Membership(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="memberships",
	)
	project = models.ForeignKey(
		"projects.Project",
		on_delete=models.CASCADE,
		related_name="memberships",
	)
	role = models.CharField(max_length=16, choices=Role.choices, default=Role.VIEWER)
	created_at = models.DateTimeField(default=timezone.now)

	class Meta:
		unique_together = ("user", "project")
		indexes = [models.Index(fields=["user", "project"])]

	def has_at_least(self, required: str) -> bool:
		return ROLE_RANK[self.role] >= ROLE_RANK[required]


class AuditLog(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="audit_entries",
	)
	action = models.CharField(max_length=64)
	target_type = models.CharField(max_length=64, blank=True, default="")
	target_id = models.CharField(max_length=64, blank=True, default="")
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(default=timezone.now, db_index=True)

	class Meta:
		indexes = [models.Index(fields=["action", "created_at"])]
