from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from es.domain import Project


class Role(str, Enum):
	viewer = "viewer"
	editor = "editor"
	admin = "admin"


class MemberItem(BaseModel):
	user_id: str
	role: str


class MemberWrite(BaseModel):
	user_id: str  # Auth0 sub
	role: Role


class ProjectCreate(BaseModel):
	name: str = Field(max_length=120)
	description: str = ""
	metadata: dict = Field(default_factory=dict)


class ProjectPatch(BaseModel):
	name: str | None = Field(default=None, max_length=120)
	description: str | None = None
	metadata: dict | None = None


class ProjectListItem(BaseModel):
	"""Shape of a read-model doc (projection output)."""

	id: str
	slug: str
	name: str
	description: str
	owner_id: str
	status: str
	metadata: dict
	members: list[MemberItem] = []
	created_at: str
	updated_at: str


class ProjectOut(BaseModel):
	id: UUID
	slug: str
	name: str
	description: str
	owner_id: str
	status: str
	metadata: dict

	@classmethod
	def from_aggregate(cls, p: Project) -> "ProjectOut":
		return cls(
			id=p.id,
			slug=p.slug,
			name=p.name,
			description=p.description,
			owner_id=p.owner_id,
			status=p.status,
			metadata=p.metadata,
		)
