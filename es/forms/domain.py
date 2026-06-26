"""Write model — Form (definition, versioned) + FormSubmission aggregates."""
import re

from eventsourcing.domain import Aggregate, event

_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str, maxlen: int = 80) -> str:
	return _SLUG.sub("-", value.lower()).strip("-")[:maxlen] or "form"


class Form(Aggregate):
	@event("Created")
	def __init__(
		self,
		owner_id: str,
		project_id: str | None,
		slug: str,
		name: str,
		description: str,
		schema: list,
		is_public: bool,
		notify_emails: list,
	):
		self.owner_id = owner_id
		self.project_id = project_id
		self.slug = slug
		self.name = name
		self.description = description
		self.schema = schema
		self.version = 1
		self.is_active = True
		self.is_public = is_public
		self.notify_emails = notify_emails

	@event("Updated")
	def update(self, changes: dict, schema: list) -> None:
		for key in ("name", "description", "is_public", "notify_emails"):
			if changes.get(key) is not None:
				setattr(self, key, changes[key])
		self.schema = schema
		self.version += 1

	@event("ActiveSet")
	def set_active(self, is_active: bool) -> None:
		self.is_active = is_active


class FormSubmission(Aggregate):
	@event("Submitted")
	def __init__(
		self,
		form_id: str,
		form_version: int,
		submitter: str | None,
		data: dict,
		ip: str | None,
		user_agent: str,
	):
		self.form_id = form_id
		self.form_version = form_version
		self.submitter = submitter
		self.data = data
		self.ip = ip
		self.user_agent = user_agent
