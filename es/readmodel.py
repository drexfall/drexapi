"""Read-model store for projections + queries.

Swappable backend: Mongo when configured, in-memory otherwise. Tests/smoke
call `set_read_store()` to force in-memory and never touch a live cluster.

Read docs are eventually consistent with the event log. With the in-process
SingleThreadedRunner (es/system.py) updates are synchronous, so reads after a
write are consistent within the process. Re-delivery is safe: all writes are
idempotent upserts keyed by project id.
"""
from functools import lru_cache
from typing import Protocol

from .config import Settings, get_settings


class ReadModelStore(Protocol):
	def upsert(self, doc: dict) -> None: ...
	def patch(self, pid: str, fields: dict) -> None: ...
	def delete(self, pid: str) -> None: ...
	def get(self, pid: str) -> dict | None: ...
	def list_for_member(self, user_id: str, limit: int, skip: int) -> list[dict]: ...
	def slug_exists(self, slug: str) -> bool: ...
	def set_member(self, pid: str, user_id: str, role: str) -> None: ...
	def remove_member(self, pid: str, user_id: str) -> None: ...
	def get_role(self, pid: str, user_id: str) -> str | None: ...
	def all(self, limit: int, skip: int) -> list[dict]: ...
	def count(self) -> int: ...


class InMemoryReadModelStore:
	def __init__(self) -> None:
		self._docs: dict[str, dict] = {}

	def upsert(self, doc: dict) -> None:
		self._docs[doc["id"]] = dict(doc)

	def patch(self, pid: str, fields: dict) -> None:
		if pid in self._docs:
			self._docs[pid].update(fields)

	def delete(self, pid: str) -> None:
		self._docs.pop(pid, None)

	def get(self, pid: str) -> dict | None:
		doc = self._docs.get(pid)
		return dict(doc) if doc else None

	def list_for_member(self, user_id: str, limit: int, skip: int) -> list[dict]:
		rows = [
			dict(d)
			for d in self._docs.values()
			if any(m["user_id"] == user_id for m in d.get("members", []))
		]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]

	def slug_exists(self, slug: str) -> bool:
		return any(d["slug"] == slug for d in self._docs.values())

	def set_member(self, pid: str, user_id: str, role: str) -> None:
		doc = self._docs.get(pid)
		if not doc:
			return
		members = [m for m in doc.get("members", []) if m["user_id"] != user_id]
		members.append({"user_id": user_id, "role": role})
		doc["members"] = members

	def remove_member(self, pid: str, user_id: str) -> None:
		doc = self._docs.get(pid)
		if not doc:
			return
		doc["members"] = [m for m in doc.get("members", []) if m["user_id"] != user_id]

	def get_role(self, pid: str, user_id: str) -> str | None:
		doc = self._docs.get(pid)
		if not doc:
			return None
		for m in doc.get("members", []):
			if m["user_id"] == user_id:
				return m["role"]
		return None

	def all(self, limit: int, skip: int) -> list[dict]:
		rows = [dict(d) for d in self._docs.values()]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]

	def count(self) -> int:
		return len(self._docs)


class MongoReadModelStore:
	"""Single `projects` collection in MONGO_DB — one doc per project.

	Unlike the legacy per-project `project_<hex>` collections, list/filter needs
	one queryable collection across all projects.
	"""

	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._client = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))
		self._coll = self._client[settings.mongo_db]["projects"]
		self._coll.create_index([("slug", ASCENDING)], unique=True)
		self._coll.create_index([("members.user_id", ASCENDING), ("created_at", ASCENDING)])

	def upsert(self, doc: dict) -> None:
		self._coll.update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)

	def patch(self, pid: str, fields: dict) -> None:
		self._coll.update_one({"_id": pid}, {"$set": fields})

	def delete(self, pid: str) -> None:
		self._coll.delete_one({"_id": pid})

	def get(self, pid: str) -> dict | None:
		return self._coll.find_one({"_id": pid}, {"_id": 0})

	def list_for_member(self, user_id: str, limit: int, skip: int) -> list[dict]:
		cur = (
			self._coll.find({"members.user_id": user_id}, {"_id": 0})
			.sort("created_at", -1)
			.skip(skip)
			.limit(limit)
		)
		return list(cur)

	def slug_exists(self, slug: str) -> bool:
		return self._coll.count_documents({"slug": slug}, limit=1) > 0

	def set_member(self, pid: str, user_id: str, role: str) -> None:
		# idempotent upsert: drop any existing entry, then add
		self._coll.update_one({"_id": pid}, {"$pull": {"members": {"user_id": user_id}}})
		self._coll.update_one(
			{"_id": pid}, {"$push": {"members": {"user_id": user_id, "role": role}}}
		)

	def remove_member(self, pid: str, user_id: str) -> None:
		self._coll.update_one({"_id": pid}, {"$pull": {"members": {"user_id": user_id}}})

	def get_role(self, pid: str, user_id: str) -> str | None:
		doc = self._coll.find_one(
			{"_id": pid, "members.user_id": user_id}, {"members.$": 1}
		)
		if not doc or not doc.get("members"):
			return None
		return doc["members"][0]["role"]

	def all(self, limit: int, skip: int) -> list[dict]:
		return list(
			self._coll.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
		)

	def count(self) -> int:
		return self._coll.count_documents({})


_override: ReadModelStore | None = None


def set_read_store(store: ReadModelStore | None) -> None:
	"""Force a store (tests/smoke). Pass None to clear and fall back to settings."""
	global _override
	_override = store
	_build_store.cache_clear()


@lru_cache
def _build_store() -> ReadModelStore:
	settings = get_settings()
	if settings.mongo_uri:
		return MongoReadModelStore(settings)
	return InMemoryReadModelStore()


def get_read_store() -> ReadModelStore:
	if _override is not None:
		return _override
	return _build_store()
