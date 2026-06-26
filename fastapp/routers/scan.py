"""Scan codes: owner CRUD (/scan-codes) + public resolver (/scan/{code_id}).

Note: legacy mounted management CRUD and the public resolver both under /scan,
which collide. Disambiguated here: management at /scan-codes, resolver at /scan.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from es.scan.app import get_scan_app
from es.scan.readmodel import get_scan_store
from fastapp.auth import Principal, require_principal


class ScanCreate(BaseModel):
	target_url: str
	label: str = ""


class ScanPatch(BaseModel):
	label: str | None = None
	target_url: str | None = None
	is_active: bool | None = None


crud = APIRouter(prefix="/scan-codes", tags=["scan"])
public = APIRouter(prefix="/scan", tags=["scan"])


def _owned_by_code(code_id: str, principal: Principal) -> dict:
	doc = get_scan_store().get_by_code(code_id)
	if not doc or (not principal.is_admin and doc["owner_id"] != principal.sub):
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Code not found")
	return doc


@crud.get("")
def list_codes(principal: Principal = Depends(require_principal),
			   limit: int = Query(50, ge=1, le=500), skip: int = Query(0, ge=0)):
	return get_scan_store().list_for(principal.sub, principal.is_admin, limit, skip)


@crud.post("", status_code=status.HTTP_201_CREATED)
def create_code(body: ScanCreate, principal: Principal = Depends(require_principal)):
	sid = get_scan_app().create(owner_id=principal.sub, target_url=body.target_url, label=body.label)
	return get_scan_store().get(str(sid))


@crud.get("/{code_id}")
def get_code(code_id: str, principal: Principal = Depends(require_principal)):
	return _owned_by_code(code_id, principal)


@crud.patch("/{code_id}")
def patch_code(code_id: str, body: ScanPatch, principal: Principal = Depends(require_principal)):
	doc = _owned_by_code(code_id, principal)
	get_scan_app().update(UUID(doc["id"]), body.model_dump(exclude_unset=True))
	return get_scan_store().get_by_code(code_id)


@crud.delete("/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_code(code_id: str, principal: Principal = Depends(require_principal)):
	# soft-delete: deactivate (ES keeps history)
	doc = _owned_by_code(code_id, principal)
	get_scan_app().update(UUID(doc["id"]), {"is_active": False})


@public.get("")
def scan_index():
	return {"title": "Scan"}


@public.get("/{code_id}")
def resolve(code_id: str):
	doc = get_scan_store().get_by_code(code_id)
	if not doc or not doc["is_active"]:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Code not found")
	get_scan_app().hit(UUID(doc["id"]))
	return RedirectResponse(doc["target_url"], status_code=status.HTTP_302_FOUND)
