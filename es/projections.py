"""Read side — projects Project events into the read-model store.

A ProcessApplication follower: for each event it reacts and writes the query
doc. Wired into a System with the Projects app in es/system.py.
"""
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication

from . import readmodel
from .domain import Project


class ProjectReadModel(ProcessApplication):
	@singledispatchmethod
	def policy(self, domain_event, processing_event):
		"""Default: ignore events we don't project."""

	@policy.register
	def _created(self, domain_event: Project.Created, processing_event):
		ts = domain_event.timestamp.isoformat()
		readmodel.get_read_store().upsert(
			{
				"id": str(domain_event.originator_id),
				"slug": domain_event.slug,
				"name": domain_event.name,
				"description": domain_event.description,
				"owner_id": domain_event.owner_id,
				"metadata": domain_event.metadata,
				"status": Project.PROVISIONING,
				# owner is auto-admin (mirrors Project.__init__)
				"members": [{"user_id": domain_event.owner_id, "role": "admin"}],
				"created_at": ts,
				"updated_at": ts,
			}
		)

	@policy.register
	def _member_set(self, domain_event: Project.MemberSet, processing_event):
		pid = str(domain_event.originator_id)
		store = readmodel.get_read_store()
		store.set_member(pid, domain_event.user_id, domain_event.role)
		store.patch(pid, {"updated_at": domain_event.timestamp.isoformat()})

	@policy.register
	def _member_removed(self, domain_event: Project.MemberRemoved, processing_event):
		pid = str(domain_event.originator_id)
		store = readmodel.get_read_store()
		store.remove_member(pid, domain_event.user_id)
		store.patch(pid, {"updated_at": domain_event.timestamp.isoformat()})

	@policy.register
	def _provisioned(self, domain_event: Project.Provisioned, processing_event):
		readmodel.get_read_store().patch(
			str(domain_event.originator_id),
			{"status": Project.READY, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _updated(self, domain_event: Project.Updated, processing_event):
		fields = {
			k: v
			for k, v in domain_event.changes.items()
			if v is not None and k in ("name", "description", "metadata")
		}
		fields["updated_at"] = domain_event.timestamp.isoformat()
		readmodel.get_read_store().patch(str(domain_event.originator_id), fields)

	@policy.register
	def _deleted(self, domain_event: Project.Deleted, processing_event):
		readmodel.get_read_store().delete(str(domain_event.originator_id))
