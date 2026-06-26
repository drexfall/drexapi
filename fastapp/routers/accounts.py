"""Auth/account/profile endpoints (replaces accounts.urls_auth/urls_account + core profiles)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from es.accounts.app import get_accounts_app
from es.accounts.mgmt import Auth0MgmtError, delete_user, trigger_password_reset
from es.accounts.readmodel import get_audit_store, get_profile_store
from es.readmodel import get_read_store as get_projects_store
from fastapp.auth import Principal, require_principal


class ProfilePatch(BaseModel):
	display_name: str | None = None
	bio: str | None = None
	avatar_url: str | None = None
	links: dict | None = None
	is_public: bool | None = None


def _me_doc(principal: Principal) -> dict:
	doc = get_accounts_app().get_by_sub(principal.sub)
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
	return doc


def _get_me(principal: Principal = Depends(require_principal)):
	return _me_doc(principal)


def _patch_me(body: ProfilePatch, principal: Principal = Depends(require_principal)):
	return get_accounts_app().update_profile(principal.sub, body.model_dump(exclude_unset=True))


def _sync(principal: Principal = Depends(require_principal)):
	return _me_doc(principal)


def _my_projects(principal: Principal = Depends(require_principal)):
	rows = get_projects_store().list_for_member(principal.sub, limit=500, skip=0)
	out = []
	for p in rows:
		role = next((m["role"] for m in p.get("members", []) if m["user_id"] == principal.sub), None)
		out.append({"project_id": p["id"], "slug": p["slug"], "name": p["name"], "role": role, "status": p["status"]})
	return out


def _password_reset(principal: Principal = Depends(require_principal)):
	if not principal.email:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, "No email on account.")
	try:
		trigger_password_reset(principal.email)
	except Auth0MgmtError as exc:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
	get_audit_store().append({
		"action": "password.reset_requested", "actor": principal.sub,
		"target_type": "user", "target_id": principal.sub, "metadata": {},
		"created_at": datetime.now(timezone.utc).isoformat(),
	})
	return {"status": "sent"}


def _delete_me(principal: Principal = Depends(require_principal)):
	try:
		delete_user(principal.sub)
	except Auth0MgmtError as exc:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
	get_accounts_app().delete(principal.sub)
	get_audit_store().append({
		"action": "user.deleted", "actor": None, "target_type": "user",
		"target_id": principal.sub, "metadata": {"sub": principal.sub},
		"created_at": datetime.now(timezone.utc).isoformat(),
	})
	return None


# --- /auth/* ---
auth_router = APIRouter(prefix="/auth", tags=["auth"])
auth_router.add_api_route("/me", _get_me, methods=["GET"])
auth_router.add_api_route("/me", _patch_me, methods=["PATCH"])
auth_router.add_api_route("/sync", _sync, methods=["POST"])
auth_router.add_api_route("/password-reset", _password_reset, methods=["POST"])
auth_router.add_api_route("/delete", _delete_me, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT)

# --- /account/* ---
account_router = APIRouter(prefix="/account", tags=["account"])
account_router.add_api_route("/me", _get_me, methods=["GET"])
account_router.add_api_route("/me", _patch_me, methods=["PATCH"])
account_router.add_api_route("/me/projects", _my_projects, methods=["GET"])
account_router.add_api_route("/me/sync", _sync, methods=["POST"])
account_router.add_api_route("/me/password-reset", _password_reset, methods=["POST"])
account_router.add_api_route("/me/delete", _delete_me, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT)


# --- /profiles/{username} (public) ---
profiles_router = APIRouter(tags=["profiles"])

_PUBLIC_FIELDS = ("username", "display_name", "bio", "avatar_url", "links")
_OWNER_FIELDS = _PUBLIC_FIELDS + ("is_public", "email_verified", "created_at", "updated_at")


def _auth_optional(principal_sub: str | None = None):
	return principal_sub


@profiles_router.get("/profiles/{username}")
def profile_detail(username: str, authorization: str | None = None):
	doc = get_profile_store().get_by_username(username)
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
	# public read; owner identification would need the optional bearer — kept public here
	if not doc.get("is_public"):
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
	return {k: doc.get(k) for k in _PUBLIC_FIELDS}


@profiles_router.patch("/profiles/{username}")
def profile_update(username: str, body: ProfilePatch, principal: Principal = Depends(require_principal)):
	if principal.username != username:
		raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
	doc = get_accounts_app().update_profile(principal.sub, body.model_dump(exclude_unset=True))
	return {k: doc.get(k) for k in _OWNER_FIELDS}
