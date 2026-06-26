"""Read models for forms (definitions) + form_submissions."""
from functools import lru_cache
from typing import Protocol

from es.config import Settings, get_settings


class FormStore(Protocol):
	def upsert(self, doc: dict) -> None: ...
	def patch(self, fid: str, fields: dict) -> None: ...
	def delete(self, fid: str) -> None: ...
	def get(self, fid: str) -> dict | None: ...
	def list_for(self, owner_id: str, is_admin: bool, limit: int, skip: int) -> list[dict]: ...
	def slug_taken(self, project_id: str | None, slug: str) -> bool: ...
	def count(self) -> int: ...


class SubmissionStore(Protocol):
	def append(self, doc: dict) -> None: ...
	def list_for_form(self, form_id: str, limit: int, skip: int) -> list[dict]: ...
	def count(self) -> int: ...


class InMemoryFormStore:
	def __init__(self) -> None:
		self._docs: dict[str, dict] = {}

	def upsert(self, doc: dict) -> None:
		self._docs[doc["id"]] = dict(doc)

	def patch(self, fid: str, fields: dict) -> None:
		if fid in self._docs:
			self._docs[fid].update(fields)

	def delete(self, fid: str) -> None:
		self._docs.pop(fid, None)

	def get(self, fid: str) -> dict | None:
		d = self._docs.get(fid)
		return dict(d) if d else None

	def list_for(self, owner_id, is_admin, limit, skip):
		rows = [dict(d) for d in self._docs.values() if is_admin or d["owner_id"] == owner_id]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]

	def slug_taken(self, project_id, slug):
		return any(d["project_id"] == project_id and d["slug"] == slug for d in self._docs.values())

	def count(self) -> int:
		return len(self._docs)


class InMemorySubmissionStore:
	def __init__(self) -> None:
		self._rows: list[dict] = []

	def append(self, doc: dict) -> None:
		self._rows.append(dict(doc))

	def list_for_form(self, form_id, limit, skip):
		rows = [dict(d) for d in self._rows if d["form"] == form_id]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]

	def count(self) -> int:
		return len(self._rows)


class MongoFormStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._coll = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))[
			settings.mongo_db
		]["forms"]
		self._coll.create_index([("owner_id", ASCENDING), ("created_at", ASCENDING)])
		self._coll.create_index([("project_id", ASCENDING), ("slug", ASCENDING)])

	def upsert(self, doc):
		self._coll.update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)

	def patch(self, fid, fields):
		self._coll.update_one({"_id": fid}, {"$set": fields})

	def delete(self, fid):
		self._coll.delete_one({"_id": fid})

	def get(self, fid):
		return self._coll.find_one({"_id": fid}, {"_id": 0})

	def list_for(self, owner_id, is_admin, limit, skip):
		q = {} if is_admin else {"owner_id": owner_id}
		return list(self._coll.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

	def slug_taken(self, project_id, slug):
		return self._coll.count_documents({"project_id": project_id, "slug": slug}, limit=1) > 0

	def count(self):
		return self._coll.count_documents({})


class MongoSubmissionStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._coll = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))[
			settings.mongo_db
		]["form_submissions"]
		self._coll.create_index([("form", ASCENDING), ("created_at", ASCENDING)])

	def append(self, doc):
		self._coll.insert_one(dict(doc))

	def list_for_form(self, form_id, limit, skip):
		return list(
			self._coll.find({"form": form_id}, {"_id": 0})
			.sort("created_at", -1)
			.skip(skip)
			.limit(limit)
		)

	def count(self):
		return self._coll.count_documents({})


_form_override: FormStore | None = None
_sub_override: SubmissionStore | None = None


def set_form_store(store):
	global _form_override
	_form_override = store
	_build_form.cache_clear()


def set_submission_store(store):
	global _sub_override
	_sub_override = store
	_build_sub.cache_clear()


@lru_cache
def _build_form() -> FormStore:
	s = get_settings()
	return MongoFormStore(s) if s.mongo_uri else InMemoryFormStore()


@lru_cache
def _build_sub() -> SubmissionStore:
	s = get_settings()
	return MongoSubmissionStore(s) if s.mongo_uri else InMemorySubmissionStore()


def get_form_store() -> FormStore:
	return _form_override if _form_override is not None else _build_form()


def get_submission_store() -> SubmissionStore:
	return _sub_override if _sub_override is not None else _build_sub()
