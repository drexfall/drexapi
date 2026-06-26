"""Write model — the Project aggregate.

Mirrors the legacy `projects.models.Project` fields and status machine, but
state lives only as a sequence of events. No ORM rows; aggregate is rebuilt by
replaying events. Read-side queries are served by projections (see projections.py).
"""
import re

from eventsourcing.domain import Aggregate, event

_SLUG_STRIP = re.compile(r"[^\w\s-]")
_SLUG_SPACE = re.compile(r"[\s_-]+")

# roles (mirror accounts.models.Role / ROLE_RANK), keyed by Auth0 sub
VIEWER = "viewer"
EDITOR = "editor"
ADMIN = "admin"
ROLE_RANK = {VIEWER: 1, EDITOR: 2, ADMIN: 3}


def role_at_least(role: str | None, required: str) -> bool:
	return ROLE_RANK.get(role or "", 0) >= ROLE_RANK[required]


def slugify(value: str, maxlen: int = 55) -> str:
	value = _SLUG_STRIP.sub("", value.lower()).strip()
	value = _SLUG_SPACE.sub("-", value)
	return value[:maxlen] or "project"


class Project(Aggregate):
	# status values match legacy Project.Status
	PROVISIONING = "provisioning"
	READY = "ready"
	DELETING = "deleting"
	FAILED = "failed"

	@event("Created")
	def __init__(self, owner_id: str, slug: str, name: str, description: str, metadata: dict):
		self.owner_id = owner_id
		self.slug = slug
		self.name = name
		self.description = description
		self.metadata = metadata
		self.status = self.PROVISIONING
		# membership keyed by Auth0 sub; owner is auto-admin
		self.members: dict[str, str] = {owner_id: ADMIN}

	@event("Provisioned")
	def mark_ready(self) -> None:
		self.status = self.READY

	@event("ProvisioningFailed")
	def mark_failed(self, reason: str = "") -> None:
		self.status = self.FAILED
		self.metadata = {**self.metadata, "failure_reason": reason}

	@event("Updated")
	def update(self, changes: dict) -> None:
		for key in ("name", "description", "metadata"):
			if changes.get(key) is not None:
				setattr(self, key, changes[key])

	@event("MemberSet")
	def set_member(self, user_id: str, role: str) -> None:
		# upsert — add or change role
		self.members = {**self.members, user_id: role}

	@event("MemberRemoved")
	def remove_member(self, user_id: str) -> None:
		self.members = {k: v for k, v in self.members.items() if k != user_id}

	@event("Deleted")
	def delete(self) -> None:
		self.status = self.DELETING
