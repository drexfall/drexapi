import uuid

from django.contrib.auth.models import User as Django_User
from django.db import models
from django.utils import timezone


# Create your models here.
class Portal(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	name = models.CharField(max_length=30)
	content = models.JSONField(default=dict)
	created_at = models.DateTimeField(default=timezone.now)


class User(Django_User):
	portal = models.ForeignKey(Portal, on_delete=models.CASCADE)
	created_at = models.DateTimeField(default=timezone.now)

	def __str__(self):
		return self.username
