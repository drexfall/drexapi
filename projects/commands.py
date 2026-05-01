from django.db import transaction
from django.utils.text import slugify

from accounts.models import Membership, Role

from . import events
from .models import Outbox, Project


class CommandError(Exception):
	pass


def _unique_slug(base: str) -> str:
	slug = slugify(base)[:55] or "project"
	candidate = slug
	i = 1
	while Project.objects.filter(slug=candidate).exists():
		i += 1
		candidate = f"{slug}-{i}"
	return candidate


@transaction.atomic
def create_project(*, owner, name: str, description: str = "", metadata: dict | None = None) -> Project:
	project = Project.objects.create(
		slug=_unique_slug(name),
		name=name,
		description=description,
		owner=owner,
		metadata=metadata or {},
		status=Project.Status.PROVISIONING,
	)
	Membership.objects.create(user=owner, project=project, role=Role.ADMIN)
	Outbox.objects.create(**events.project_created(project).to_outbox())
	return project


@transaction.atomic
def update_project(project: Project, *, changes: dict) -> Project:
	allowed = {"name", "description", "metadata"}
	applied: dict = {}
	for k, v in changes.items():
		if k not in allowed:
			continue
		setattr(project, k, v)
		applied[k] = v
	if not applied:
		return project
	project.save(update_fields=[*applied.keys(), "updated_at"])
	Outbox.objects.create(**events.project_updated(project, applied).to_outbox())
	return project


@transaction.atomic
def delete_project(project: Project) -> None:
	project_id = project.id
	project.status = Project.Status.DELETING
	project.save(update_fields=["status", "updated_at"])
	Outbox.objects.create(**events.project_deleted(project_id).to_outbox())
	project.delete()


@transaction.atomic
def add_member(project: Project, user, role: str) -> Membership:
	m, _ = Membership.objects.update_or_create(
		user=user, project=project, defaults={"role": role}
	)
	Outbox.objects.create(**events.member_added(project.id, user.pk, role).to_outbox())
	return m


@transaction.atomic
def remove_member(project: Project, user) -> None:
	deleted, _ = Membership.objects.filter(user=user, project=project).delete()
	if deleted:
		Outbox.objects.create(**events.member_removed(project.id, user.pk).to_outbox())
