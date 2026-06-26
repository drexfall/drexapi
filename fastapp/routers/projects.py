from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from es import readmodel
from es.application import CommandError, ProjectNotFound, Projects
from es.domain import ADMIN, EDITOR, VIEWER, role_at_least
from es.system import get_projects_app
from fastapp.auth import Principal, require_principal
from fastapp.schemas import (
	MemberItem,
	MemberWrite,
	ProjectCreate,
	ProjectListItem,
	ProjectOut,
	ProjectPatch,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _app() -> Projects:
	return get_projects_app()


@dataclass
class RoleContext:
	pid: UUID
	principal: Principal
	role: str
	doc: dict


def require_role(minimum: str):
	"""Dependency factory — gate a project route on the caller's membership role.

	404 if the project doesn't exist, 403 if the caller isn't a member or lacks
	the required role. Role comes from the read model (eventually consistent).
	"""

	def dep(pid: UUID, principal: Principal = Depends(require_principal)) -> RoleContext:
		store = readmodel.get_read_store()
		doc = store.get(str(pid))
		if doc is None:
			raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
		role = store.get_role(str(pid), principal.sub)
		if not role_at_least(role, minimum):
			raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role for this project")
		return RoleContext(pid=pid, principal=principal, role=role or "", doc=doc)

	return dep


# --- project CRUD ---


@router.post("", response_model=ProjectOut, status_code=status.HTTP_202_ACCEPTED)
def create_project(
	body: ProjectCreate,
	principal: Principal = Depends(require_principal),
	app: Projects = Depends(_app),
):
	pid = app.create(
		owner_id=principal.sub,
		name=body.name,
		description=body.description,
		metadata=body.metadata,
	)
	return ProjectOut.from_aggregate(app.get(pid))


@router.get("", response_model=list[ProjectListItem])
def list_projects(
	principal: Principal = Depends(require_principal),
	limit: int = Query(default=50, ge=1, le=500),
	skip: int = Query(default=0, ge=0),
):
	# every project the caller belongs to (owner is a member), newest first
	return readmodel.get_read_store().list_for_member(principal.sub, limit=limit, skip=skip)


@router.get("/{pid}", response_model=ProjectOut)
def get_project(ctx: RoleContext = Depends(require_role(VIEWER)), app: Projects = Depends(_app)):
	try:
		return ProjectOut.from_aggregate(app.get(ctx.pid))
	except ProjectNotFound:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")


@router.patch("/{pid}", response_model=ProjectOut)
def patch_project(
	body: ProjectPatch,
	ctx: RoleContext = Depends(require_role(EDITOR)),
	app: Projects = Depends(_app),
):
	return ProjectOut.from_aggregate(app.update(ctx.pid, body.model_dump(exclude_unset=True)))


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(ctx: RoleContext = Depends(require_role(ADMIN)), app: Projects = Depends(_app)):
	app.delete(ctx.pid)


# --- membership ---


@router.get("/{pid}/members", response_model=list[MemberItem])
def list_members(ctx: RoleContext = Depends(require_role(VIEWER))):
	return ctx.doc.get("members", [])


@router.post("/{pid}/members", response_model=MemberItem, status_code=status.HTTP_201_CREATED)
def add_member(
	body: MemberWrite,
	ctx: RoleContext = Depends(require_role(ADMIN)),
	app: Projects = Depends(_app),
):
	try:
		app.add_member(ctx.pid, body.user_id, body.role.value)
	except CommandError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
	return MemberItem(user_id=body.user_id, role=body.role.value)


@router.delete("/{pid}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
	user_id: str,
	ctx: RoleContext = Depends(require_role(ADMIN)),
	app: Projects = Depends(_app),
):
	try:
		app.remove_member(ctx.pid, user_id)
	except CommandError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
