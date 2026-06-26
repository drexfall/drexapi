"""Read model for scan codes (id-keyed; code_id + owner indexed)."""
from functools import lru_cache
from typing import Protocol

from es.config import Settings, get_settings


class ScanStore(Protocol):
	def upsert(self, doc: dict) -> None: ...
	def patch(self, sid: str, fields: dict) -> None: ...
	def get(self, sid: str) -> dict | None: ...
	def get_by_code(self, code_id: str) -> dict | None: ...
	def code_exists(self, code_id: str) -> bool: ...
	def list_for(self, owner_id: str, is_admin: bool, limit: int, skip: int) -> list[dict]: ...


class InMemoryScanStore:
	def __init__(self) -> None:
		self._docs: dict[str, dict] = {}

	def upsert(self, doc):
		self._docs[doc["id"]] = dict(doc)

	def patch(self, sid, fields):
		if sid in self._docs:
			self._docs[sid].update(fields)

	def get(self, sid):
		d = self._docs.get(sid)
		return dict(d) if d else None

	def get_by_code(self, code_id):
		return next((dict(d) for d in self._docs.values() if d["code_id"] == code_id), None)

	def code_exists(self, code_id):
		return any(d["code_id"] == code_id for d in self._docs.values())

	def list_for(self, owner_id, is_admin, limit, skip):
		rows = [dict(d) for d in self._docs.values() if is_admin or d["owner_id"] == owner_id]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]


class MongoScanStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._coll = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))[
			settings.mongo_db
		]["scan_codes"]
		self._coll.create_index([("code_id", ASCENDING)], unique=True)
		self._coll.create_index([("owner_id", ASCENDING), ("created_at", ASCENDING)])

	def upsert(self, doc):
		self._coll.update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)

	def patch(self, sid, fields):
		self._coll.update_one({"_id": sid}, {"$set": fields})

	def get(self, sid):
		return self._coll.find_one({"_id": sid}, {"_id": 0})

	def get_by_code(self, code_id):
		return self._coll.find_one({"code_id": code_id}, {"_id": 0})

	def code_exists(self, code_id):
		return self._coll.count_documents({"code_id": code_id}, limit=1) > 0

	def list_for(self, owner_id, is_admin, limit, skip):
		q = {} if is_admin else {"owner_id": owner_id}
		return list(self._coll.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))


_override: ScanStore | None = None


def set_scan_store(store):
	global _override
	_override = store
	_build.cache_clear()


@lru_cache
def _build() -> ScanStore:
	s = get_settings()
	return MongoScanStore(s) if s.mongo_uri else InMemoryScanStore()


def get_scan_store() -> ScanStore:
	return _override if _override is not None else _build()
