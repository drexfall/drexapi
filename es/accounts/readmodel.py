"""Read models for accounts: profiles (id-keyed; sub/username indexed) + append-only audit."""
from functools import lru_cache
from typing import Protocol

from es.config import Settings, get_settings


class ProfileStore(Protocol):
	def upsert(self, doc: dict) -> None: ...
	def patch(self, pid: str, fields: dict) -> None: ...
	def delete(self, pid: str) -> None: ...
	def get_by_id(self, pid: str) -> dict | None: ...
	def get_by_sub(self, sub: str) -> dict | None: ...
	def get_by_username(self, username: str) -> dict | None: ...
	def username_exists(self, username: str) -> bool: ...
	def list_all(self, limit: int, skip: int) -> list[dict]: ...
	def count(self) -> int: ...


class AuditStore(Protocol):
	def append(self, entry: dict) -> None: ...
	def list(self, limit: int, skip: int) -> list[dict]: ...
	def count(self) -> int: ...


class InMemoryProfileStore:
	def __init__(self) -> None:
		self._by_id: dict[str, dict] = {}

	def upsert(self, doc: dict) -> None:
		self._by_id[doc["id"]] = dict(doc)

	def patch(self, pid: str, fields: dict) -> None:
		if pid in self._by_id:
			self._by_id[pid].update(fields)

	def delete(self, pid: str) -> None:
		self._by_id.pop(pid, None)

	def get_by_id(self, pid: str) -> dict | None:
		d = self._by_id.get(pid)
		return dict(d) if d else None

	def get_by_sub(self, sub: str) -> dict | None:
		return next((dict(d) for d in self._by_id.values() if d["sub"] == sub), None)

	def get_by_username(self, username: str) -> dict | None:
		return next((dict(d) for d in self._by_id.values() if d["username"] == username), None)

	def username_exists(self, username: str) -> bool:
		return any(d["username"] == username for d in self._by_id.values())

	def list_all(self, limit: int, skip: int) -> list[dict]:
		rows = sorted(self._by_id.values(), key=lambda d: d["created_at"], reverse=True)
		return [dict(d) for d in rows[skip : skip + limit]]

	def count(self) -> int:
		return len(self._by_id)


class InMemoryAuditStore:
	def __init__(self) -> None:
		self._rows: list[dict] = []

	def append(self, entry: dict) -> None:
		self._rows.append(dict(entry))

	def list(self, limit: int, skip: int) -> list[dict]:
		return list(reversed(self._rows))[skip : skip + limit]

	def count(self) -> int:
		return len(self._rows)


class MongoProfileStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._coll = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))[
			settings.mongo_db
		]["profiles"]
		self._coll.create_index([("sub", ASCENDING)], unique=True)
		self._coll.create_index([("username", ASCENDING)], unique=True)

	def upsert(self, doc: dict) -> None:
		self._coll.update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)

	def patch(self, pid: str, fields: dict) -> None:
		self._coll.update_one({"_id": pid}, {"$set": fields})

	def delete(self, pid: str) -> None:
		self._coll.delete_one({"_id": pid})

	def get_by_id(self, pid: str) -> dict | None:
		return self._coll.find_one({"_id": pid}, {"_id": 0})

	def get_by_sub(self, sub: str) -> dict | None:
		return self._coll.find_one({"sub": sub}, {"_id": 0})

	def get_by_username(self, username: str) -> dict | None:
		return self._coll.find_one({"username": username}, {"_id": 0})

	def username_exists(self, username: str) -> bool:
		return self._coll.count_documents({"username": username}, limit=1) > 0

	def list_all(self, limit: int, skip: int) -> list[dict]:
		return list(self._coll.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

	def count(self) -> int:
		return self._coll.count_documents({})


class MongoAuditStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._coll = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))[
			settings.mongo_db
		]["audit"]
		self._coll.create_index([("created_at", ASCENDING)])

	def append(self, entry: dict) -> None:
		self._coll.insert_one(dict(entry))

	def list(self, limit: int, skip: int) -> list[dict]:
		return list(self._coll.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))

	def count(self) -> int:
		return self._coll.count_documents({})


_profile_override: ProfileStore | None = None
_audit_override: AuditStore | None = None


def set_profile_store(store: ProfileStore | None) -> None:
	global _profile_override
	_profile_override = store
	_build_profile.cache_clear()


def set_audit_store(store: AuditStore | None) -> None:
	global _audit_override
	_audit_override = store
	_build_audit.cache_clear()


@lru_cache
def _build_profile() -> ProfileStore:
	s = get_settings()
	return MongoProfileStore(s) if s.mongo_uri else InMemoryProfileStore()


@lru_cache
def _build_audit() -> AuditStore:
	s = get_settings()
	return MongoAuditStore(s) if s.mongo_uri else InMemoryAuditStore()


def get_profile_store() -> ProfileStore:
	return _profile_override if _profile_override is not None else _build_profile()


def get_audit_store() -> AuditStore:
	return _audit_override if _audit_override is not None else _build_audit()
