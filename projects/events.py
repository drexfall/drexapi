from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Event:
	event_type: str
	aggregate_id: str
	payload: dict[str, Any] = field(default_factory=dict)

	def to_outbox(self) -> dict[str, Any]:
		return {
			"event_type": self.event_type,
			"aggregate_id": self.aggregate_id,
			"payload": self.payload,
		}


def project_created(project) -> Event:
	return Event(
		event_type="project.created",
		aggregate_id=str(project.id),
		payload={
			"id": str(project.id),
			"slug": project.slug,
			"name": project.name,
			"description": project.description,
			"owner_id": project.owner_id,
			"metadata": project.metadata,
			"created_at": project.created_at.isoformat(),
		},
	)


def project_updated(project, changed: dict) -> Event:
	return Event(
		event_type="project.updated",
		aggregate_id=str(project.id),
		payload={"id": str(project.id), "changed": changed},
	)


def project_deleted(project_id) -> Event:
	return Event(
		event_type="project.deleted",
		aggregate_id=str(project_id),
		payload={"id": str(project_id)},
	)


def member_added(project_id, user_id, role: str) -> Event:
	return Event(
		event_type="project.member_added",
		aggregate_id=str(project_id),
		payload={"project_id": str(project_id), "user_id": user_id, "role": role},
	)


def member_removed(project_id, user_id) -> Event:
	return Event(
		event_type="project.member_removed",
		aggregate_id=str(project_id),
		payload={"project_id": str(project_id), "user_id": user_id},
	)
