"""Platform-admin endpoints (replaces administration app). Gated by require_admin."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from es.accounts.app import get_accounts_app
from es.accounts.mgmt import Auth0MgmtError, delete_user
from es.accounts.readmodel import get_audit_store, get_profile_store
from es.application import ProjectNotFound
from es.forms.readmodel import get_form_store, get_submission_store
from es.readmodel import get_read_store as get_projects_store
from es.system import get_projects_app
from fastapp.auth import Principal, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleAssign(BaseModel):
	user_id: str  # Auth0 sub
	project_id: str
	role: str


class AdminUserPatch(BaseModel):
	display_name: str | None = None
	bio: str | None = None
	is_public: bool | None = None
	is_admin: bool | None = None


def _now() -> str:
	return datetime.now(timezone.utc).isoformat()


@router.get("/stats")
def stats(principal: Principal = Depends(require_admin)):
	memberships = sum(len(p.get("members", [])) for p in get_projects_store().all(10_000, 0))
	return {
		"users": get_profile_store().count(),
		"projects": get_projects_store().count(),
		"memberships": memberships,
		"forms": get_form_store().count(),
		"submissions": get_submission_store().count(),
	}


@router.post("/roles/assign")
def assign_role(body: RoleAssign, principal: Principal = Depends(require_admin)):
	try:
		get_projects_app().add_member(UUID(body.project_id), body.user_id, body.role)
	except ProjectNotFound:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
	get_audit_store().append({
		"action": "admin.role_assigned", "actor": principal.sub, "target_type": "membership",
		"target_id": f"{body.project_id}:{body.user_id}",
		"metadata": {"user_id": body.user_id, "project_id": body.project_id, "role": body.role},
		"created_at": _now(),
	})
	return {"user_id": body.user_id, "project_id": body.project_id, "role": body.role}


@router.get("/users")
def list_users(principal: Principal = Depends(require_admin),
			   limit: int = Query(100, ge=1, le=1000), skip: int = Query(0, ge=0)):
	return get_profile_store().list_all(limit, skip)


@router.get("/users/{username}")
def get_user(username: str, principal: Principal = Depends(require_admin)):
	doc = get_profile_store().get_by_username(username)
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
	return doc


@router.patch("/users/{username}")
def patch_user(username: str, body: AdminUserPatch, principal: Principal = Depends(require_admin)):
	doc = get_profile_store().get_by_username(username)
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
	app = get_accounts_app()
	changes = body.model_dump(exclude_unset=True)
	if "is_admin" in changes:
		app.set_admin(doc["sub"], changes.pop("is_admin"))
	if changes:
		app.update_profile(doc["sub"], changes)
	return get_profile_store().get_by_username(username)


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_endpoint(username: str, principal: Principal = Depends(require_admin)):
	doc = get_profile_store().get_by_username(username)
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
	try:
		delete_user(doc["sub"])
	except Auth0MgmtError as exc:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
	get_accounts_app().delete(doc["sub"])
	get_audit_store().append({
		"action": "user.deleted", "actor": principal.sub, "target_type": "user",
		"target_id": doc["sub"], "metadata": {"sub": doc["sub"]}, "created_at": _now(),
	})


@router.get("/memberships")
def list_memberships(principal: Principal = Depends(require_admin),
					 limit: int = Query(500, ge=1, le=2000), skip: int = Query(0, ge=0)):
	out = []
	for p in get_projects_store().all(10_000, 0):
		for m in p.get("members", []):
			out.append({
				"project_id": p["id"], "project_name": p["name"],
				"user_id": m["user_id"], "role": m["role"],
			})
	return out[skip : skip + limit]


@router.get("/audit")
def list_audit(principal: Principal = Depends(require_admin),
			   limit: int = Query(200, ge=1, le=1000), skip: int = Query(0, ge=0)):
	return get_audit_store().list(limit, skip)
