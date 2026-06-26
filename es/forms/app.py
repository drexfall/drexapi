"""Forms application + projection + system. One Forms app owns both Form and
FormSubmission aggregates; one projection follows it and writes both read models."""
from functools import lru_cache
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication, SingleThreadedRunner, System

from es.application import CommandError, ProjectNotFound
from es.config import get_settings

from . import readmodel
from .domain import Form, FormSubmission, slugify
from .validation import validate_schema, validate_submission


class FormNotFound(ProjectNotFound):
	pass


class Forms(Application):
	def create_form(self, *, owner_id, name, slug=None, project_id=None, description="",
					schema=None, is_public=False, notify_emails=None) -> UUID:
		schema = validate_schema(schema or [])
		slug = slugify(slug or name)
		if readmodel.get_form_store().slug_taken(project_id, slug):
			raise CommandError(f"slug already used in this project: {slug}")
		form = Form(
			owner_id=owner_id, project_id=project_id, slug=slug, name=name,
			description=description, schema=schema, is_public=is_public,
			notify_emails=notify_emails or [],
		)
		self.save(form)
		return form.id

	def get(self, fid: UUID) -> Form:
		try:
			return self.repository.get(fid)
		except Exception as exc:
			raise FormNotFound(str(fid)) from exc

	def update_form(self, fid: UUID, changes: dict) -> Form:
		form = self.get(fid)
		schema = validate_schema(changes["schema"]) if changes.get("schema") is not None else form.schema
		form.update(changes, schema)
		self.save(form)
		return form

	def set_active(self, fid: UUID, is_active: bool) -> Form:
		form = self.get(fid)
		form.set_active(is_active)
		self.save(form)
		return form

	def submit(self, fid: UUID, *, data, submitter=None, ip=None, user_agent="") -> UUID:
		doc = readmodel.get_form_store().get(str(fid))
		if not doc or not doc["is_active"]:
			raise FormNotFound(str(fid))
		clean = validate_submission(doc["schema"], data)
		submission = FormSubmission(
			form_id=str(fid), form_version=doc["version"], submitter=submitter,
			data=clean, ip=ip, user_agent=user_agent[:512],
		)
		self.save(submission)
		return submission.id


def _form_doc(e) -> dict:
	ts = e.timestamp.isoformat()
	return {
		"id": str(e.originator_id), "project_id": e.project_id, "owner_id": e.owner_id,
		"slug": e.slug, "name": e.name, "description": e.description, "schema": e.schema,
		"version": 1, "is_active": True, "is_public": e.is_public,
		"notify_emails": e.notify_emails, "created_at": ts, "updated_at": ts,
	}


class FormReadModel(ProcessApplication):
	@singledispatchmethod
	def policy(self, domain_event, processing_event):
		"""ignore"""

	@policy.register
	def _created(self, domain_event: Form.Created, processing_event):
		readmodel.get_form_store().upsert(_form_doc(domain_event))

	@policy.register
	def _updated(self, domain_event: Form.Updated, processing_event):
		fields = {
			k: v for k, v in domain_event.changes.items()
			if v is not None and k in ("name", "description", "is_public", "notify_emails")
		}
		fields["schema"] = domain_event.schema
		fields["updated_at"] = domain_event.timestamp.isoformat()
		# version bump mirrors aggregate (+1 per Updated)
		store = readmodel.get_form_store()
		doc = store.get(str(domain_event.originator_id))
		if doc:
			fields["version"] = doc["version"] + 1
		store.patch(str(domain_event.originator_id), fields)

	@policy.register
	def _active(self, domain_event: Form.ActiveSet, processing_event):
		readmodel.get_form_store().patch(
			str(domain_event.originator_id),
			{"is_active": domain_event.is_active, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _submitted(self, domain_event: FormSubmission.Submitted, processing_event):
		readmodel.get_submission_store().append(
			{
				"id": str(domain_event.originator_id),
				"form": domain_event.form_id,
				"form_version": domain_event.form_version,
				"submitter": domain_event.submitter,
				"data": domain_event.data,
				"created_at": domain_event.timestamp.isoformat(),
			}
		)


@lru_cache
def get_runner() -> SingleThreadedRunner:
	system = System(pipes=[[Forms, FormReadModel]])
	runner = SingleThreadedRunner(system, env=get_settings().es_env())
	runner.start()
	return runner


def get_forms_app() -> Forms:
	return get_runner().get(Forms)
