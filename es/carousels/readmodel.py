"""Read-model store for carousels. Swappable: Mongo when configured, else
in-memory. Forced to in-memory in tests via set_carousel_store()."""
from functools import lru_cache
from typing import Protocol

from es.config import Settings, get_settings


class CarouselStore(Protocol):
	def upsert(self, doc: dict) -> None: ...
	def patch(self, cid: str, fields: dict) -> None: ...
	def get(self, cid: str) -> dict | None: ...
	def list(self, status: str | None, limit: int, skip: int) -> list[dict]: ...
	def set_slide_image(self, cid: str, order: int, image_url: str, file_id: str) -> None: ...


class InMemoryCarouselStore:
	def __init__(self) -> None:
		self._docs: dict[str, dict] = {}

	def upsert(self, doc: dict) -> None:
		self._docs[doc["id"]] = dict(doc)

	def patch(self, cid: str, fields: dict) -> None:
		if cid in self._docs:
			self._docs[cid].update(fields)

	def get(self, cid: str) -> dict | None:
		doc = self._docs.get(cid)
		return dict(doc) if doc else None

	def list(self, status: str | None, limit: int, skip: int) -> list[dict]:
		rows = [dict(d) for d in self._docs.values() if status is None or d["status"] == status]
		rows.sort(key=lambda d: d["created_at"], reverse=True)
		return rows[skip : skip + limit]

	def set_slide_image(self, cid: str, order: int, image_url: str, file_id: str) -> None:
		doc = self._docs.get(cid)
		if not doc:
			return
		for s in doc.get("slides", []):
			if s["order"] == order:
				s["image_url"] = image_url
				s["file_id"] = file_id


class MongoCarouselStore:
	def __init__(self, settings: Settings) -> None:
		from pymongo import ASCENDING, MongoClient
		from pymongo.server_api import ServerApi

		self._client = MongoClient(settings.mongo_uri, server_api=ServerApi("1"))
		self._coll = self._client[settings.mongo_db]["carousels"]
		self._coll.create_index([("status", ASCENDING), ("created_at", ASCENDING)])

	def upsert(self, doc: dict) -> None:
		self._coll.update_one({"_id": doc["id"]}, {"$set": doc}, upsert=True)

	def patch(self, cid: str, fields: dict) -> None:
		self._coll.update_one({"_id": cid}, {"$set": fields})

	def get(self, cid: str) -> dict | None:
		return self._coll.find_one({"_id": cid}, {"_id": 0})

	def list(self, status: str | None, limit: int, skip: int) -> list[dict]:
		query = {} if status is None else {"status": status}
		cur = (
			self._coll.find(query, {"_id": 0})
			.sort("created_at", -1)
			.skip(skip)
			.limit(limit)
		)
		return list(cur)

	def set_slide_image(self, cid: str, order: int, image_url: str, file_id: str) -> None:
		self._coll.update_one(
			{"_id": cid},
			{"$set": {"slides.$[s].image_url": image_url, "slides.$[s].file_id": file_id}},
			array_filters=[{"s.order": order}],
		)


_override: CarouselStore | None = None


def set_carousel_store(store: CarouselStore | None) -> None:
	global _override
	_override = store
	_build_store.cache_clear()


@lru_cache
def _build_store() -> CarouselStore:
	settings = get_settings()
	if settings.mongo_uri:
		return MongoCarouselStore(settings)
	return InMemoryCarouselStore()


def get_carousel_store() -> CarouselStore:
	if _override is not None:
		return _override
	return _build_store()
