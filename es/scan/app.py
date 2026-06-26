"""Scan application + projection + system."""
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication, SingleThreadedRunner, System

from es.application import ProjectNotFound
from es.config import get_settings

from . import readmodel
from .domain import ScanCode, gen_code


class ScanNotFound(ProjectNotFound):
	pass


class Scan(Application):
	def create(self, *, owner_id, target_url, label="") -> UUID:
		code_id = gen_code()
		while readmodel.get_scan_store().code_exists(code_id):
			code_id = gen_code()
		code = ScanCode(owner_id=owner_id, code_id=code_id, label=label, target_url=target_url)
		self.save(code)
		return code.id

	def get(self, sid: UUID) -> ScanCode:
		try:
			return self.repository.get(sid)
		except Exception as exc:
			raise ScanNotFound(str(sid)) from exc

	def update(self, sid: UUID, changes: dict) -> ScanCode:
		code = self.get(sid)
		code.update(changes)
		self.save(code)
		return code

	def hit(self, sid: UUID) -> None:
		code = self.get(sid)
		code.hit(datetime.now(timezone.utc).isoformat())
		self.save(code)


class ScanReadModel(ProcessApplication):
	@singledispatchmethod
	def policy(self, domain_event, processing_event):
		"""ignore"""

	@policy.register
	def _created(self, domain_event: ScanCode.Created, processing_event):
		ts = domain_event.timestamp.isoformat()
		readmodel.get_scan_store().upsert(
			{
				"id": str(domain_event.originator_id),
				"code_id": domain_event.code_id,
				"owner_id": domain_event.owner_id,
				"label": domain_event.label,
				"target_url": domain_event.target_url,
				"is_active": True,
				"hit_count": 0,
				"last_hit_at": None,
				"created_at": ts,
				"updated_at": ts,
			}
		)

	@policy.register
	def _updated(self, domain_event: ScanCode.Updated, processing_event):
		fields = {
			k: v for k, v in domain_event.changes.items()
			if v is not None and k in ("label", "target_url", "is_active")
		}
		fields["updated_at"] = domain_event.timestamp.isoformat()
		readmodel.get_scan_store().patch(str(domain_event.originator_id), fields)

	@policy.register
	def _hit(self, domain_event: ScanCode.Hit, processing_event):
		store = readmodel.get_scan_store()
		doc = store.get(str(domain_event.originator_id))
		if doc:
			store.patch(
				str(domain_event.originator_id),
				{"hit_count": doc["hit_count"] + 1, "last_hit_at": domain_event.at},
			)


@lru_cache
def get_runner() -> SingleThreadedRunner:
	system = System(pipes=[[Scan, ScanReadModel]])
	runner = SingleThreadedRunner(system, env=get_settings().es_env())
	runner.start()
	return runner


def get_scan_app() -> Scan:
	return get_runner().get(Scan)
