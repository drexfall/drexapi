"""Application service — the command side. Wraps the event store + repository."""
from uuid import UUID

from eventsourcing.application import Application

from . import readmodel
from .domain import ROLE_RANK, Project, slugify


class ProjectNotFound(Exception):
	pass


class CommandError(Exception):
	pass


class Projects(Application):
	def create(self, *, owner_id: str, name: str, description: str = "", metadata: dict | None = None) -> UUID:
		project = Project(
			owner_id=str(owner_id),
			slug=self._unique_slug(name),
			name=name,
			description=description or "",
			metadata=metadata or {},
		)
		self.save(project)
		return project.id

	@staticmethod
	def _unique_slug(name: str) -> str:
		# Consults the read model (synchronously consistent under the in-process
		# runner). Mongo also enforces a unique index as the hard backstop.
		store = readmodel.get_read_store()
		base = slugify(name)
		slug = base
		i = 1
		while store.slug_exists(slug):
			i += 1
			slug = f"{base}-{i}"
		return slug

	def get(self, pid: UUID) -> Project:
		try:
			return self.repository.get(pid)
		except Exception as exc:  # AggregateNotFound + bad-id
			raise ProjectNotFound(str(pid)) from exc

	def mark_ready(self, pid: UUID) -> None:
		project = self.get(pid)
		project.mark_ready()
		self.save(project)

	def update(self, pid: UUID, changes: dict) -> Project:
		project = self.get(pid)
		project.update(changes)
		self.save(project)
		return project

	def add_member(self, pid: UUID, user_id: str, role: str) -> Project:
		if role not in ROLE_RANK:
			raise CommandError(f"unknown role: {role}")
		project = self.get(pid)
		project.set_member(user_id, role)
		self.save(project)
		return project

	def remove_member(self, pid: UUID, user_id: str) -> None:
		project = self.get(pid)
		if user_id == project.owner_id:
			raise CommandError("cannot remove the project owner")
		project.remove_member(user_id)
		self.save(project)

	def delete(self, pid: UUID) -> None:
		project = self.get(pid)
		project.delete()
		self.save(project)
