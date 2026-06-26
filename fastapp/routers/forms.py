"""Form definitions + submissions (replaces forms.views.FormDefinitionViewSet)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from es.application import CommandError
from es.forms.app import FormNotFound, get_forms_app
from es.forms.readmodel import get_form_store, get_submission_store
from es.forms.validation import FormValidationError
from fastapp.auth import Principal, require_principal
from fastapp.auth_optional import optional_principal

router = APIRouter(prefix="/forms", tags=["forms"])


class FormCreate(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	name: str = Field(max_length=120)
	slug: str | None = None
	project_id: str | None = None
	description: str = ""
	form_schema: Annotated[list, Field(validation_alias="schema")] = []
	is_public: bool = False
	notify_emails: list[str] = Field(default_factory=list)


class FormPatch(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	name: str | None = None
	description: str | None = None
	# non-union so the alias is unambiguous; presence detected via exclude_unset
	form_schema: Annotated[list, Field(validation_alias="schema")] = []
	is_public: bool | None = None
	notify_emails: list[str] | None = None
	is_active: bool | None = None


class SubmissionWrite(BaseModel):
	data: dict


def _owned_or_404(fid: UUID, principal: Principal) -> dict:
	doc = get_form_store().get(str(fid))
	if not doc:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
	if not principal.is_admin and doc["owner_id"] != principal.sub:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
	return doc


@router.get("")
def list_forms(principal: Principal = Depends(require_principal),
			   limit: int = Query(50, ge=1, le=500), skip: int = Query(0, ge=0)):
	return get_form_store().list_for(principal.sub, principal.is_admin, limit, skip)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_form(body: FormCreate, principal: Principal = Depends(require_principal)):
	try:
		fid = get_forms_app().create_form(
			owner_id=principal.sub, name=body.name, slug=body.slug, project_id=body.project_id,
			description=body.description, schema=body.form_schema, is_public=body.is_public,
			notify_emails=body.notify_emails,
		)
	except FormValidationError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.detail)
	except CommandError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
	return get_form_store().get(str(fid))


@router.get("/{fid}")
def get_form(fid: UUID, principal: Principal = Depends(require_principal)):
	return _owned_or_404(fid, principal)


@router.patch("/{fid}")
def patch_form(fid: UUID, body: FormPatch, principal: Principal = Depends(require_principal)):
	_owned_or_404(fid, principal)
	changes = body.model_dump(exclude_unset=True)
	if "form_schema" in changes:
		changes["schema"] = changes.pop("form_schema")
	try:
		if "is_active" in changes:
			get_forms_app().set_active(fid, changes.pop("is_active"))
		if changes:
			get_forms_app().update_form(fid, changes)
	except FormValidationError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.detail)
	return get_form_store().get(str(fid))


@router.get("/{fid}/submissions")
def list_submissions(fid: UUID, principal: Principal = Depends(require_principal),
					 limit: int = Query(500, ge=1, le=1000), skip: int = Query(0, ge=0)):
	_owned_or_404(fid, principal)
	return get_submission_store().list_for_form(str(fid), limit, skip)


@router.post("/{fid}/submit", status_code=status.HTTP_201_CREATED)
def submit(fid: UUID, body: SubmissionWrite, request: Request,
		   principal: Principal | None = Depends(optional_principal)):
	doc = get_form_store().get(str(fid))
	if not doc or not doc["is_active"]:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
	if not doc["is_public"] and principal is None:
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
	xff = request.headers.get("x-forwarded-for")
	ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
	try:
		sid = get_forms_app().submit(
			fid, data=body.data, submitter=(principal.sub if principal else None),
			ip=ip, user_agent=request.headers.get("user-agent", ""),
		)
	except FormValidationError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.detail)
	except FormNotFound:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
	subs = get_submission_store().list_for_form(str(fid), 1, 0)
	return next((s for s in subs if s["id"] == str(sid)), {"id": str(sid)})
