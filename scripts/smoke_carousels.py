"""Smoke test for slice 4 — carousel aggregate + async render reaction + publish.

In-memory event store + in-memory read store + fake renderer/publisher. No
Celery, no WeasyPrint, no ImageKit, no Meta.

Run: PYTHONPATH=. .venv/bin/python scripts/smoke_carousels.py
"""
import os

os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
os.environ["SQLITE_DBNAME"] = ":memory:"

from es.application import CommandError  # noqa: E402
from es.carousels.application import Carousels  # noqa: E402
from es.carousels.domain import Carousel  # noqa: E402
from es.carousels.pipeline import FakePublisher, LocalRenderer, publish_carousel, run_render  # noqa: E402
from es.carousels.readmodel import InMemoryCarouselStore, get_carousel_store, set_carousel_store  # noqa: E402
from es.carousels.system import get_runner  # noqa: E402

PAYLOAD = [
	{
		"headline": "Big News Today",
		"summary": "things happened",
		"category": "tech",
		"sources": ["reuters"],
		"credibility": 0.9,
		"slides": [
			{"type": "cover", "title": "Big News"},
			{"type": "narrative", "body": "details"},
			{"type": "outro", "cta": "follow"},
		],
	}
]


def main() -> None:
	set_carousel_store(InMemoryCarouselStore())
	app: Carousels = get_runner().get(Carousels)
	store = get_carousel_store()

	# --- ingest ---
	result = app.ingest_batch(source="newsscraper", run_date="2026-06-20", carousels=PAYLOAD)
	cid = result["carousel_ids"][0]
	doc = store.get(cid)
	assert doc is not None and doc["status"] == "pending", doc
	assert len(doc["slides"]) == 3
	assert doc["slides"][0]["slide_type"] == "cover"
	assert all(s["image_url"] == "" for s in doc["slides"]), "slides should start unrendered"

	# --- render worker feeds results back as events ---
	from uuid import UUID

	run_render(app, UUID(cid), LocalRenderer())
	doc = store.get(cid)
	assert doc["status"] == "ready", doc["status"]
	assert all(s["image_url"].startswith("local://") for s in doc["slides"]), doc["slides"]

	# event log proves the full async story
	stored = list(app.repository.event_store.get(UUID(cid)))
	names = [type(e).__name__ for e in stored]
	assert names == ["Ingested", "SlideRendered", "SlideRendered", "SlideRendered", "RenderCompleted"], names

	# --- approve only from ready ---
	app.approve(UUID(cid))
	assert store.get(cid)["status"] == "approved"

	# --- publish (synchronous side-effect -> event) ---
	pdoc = store.get(cid)
	publish_carousel(app, FakePublisher(), UUID(cid), pdoc, caption="hi")
	doc = store.get(cid)
	assert doc["status"] == "published", doc["status"]
	assert doc["ig_media_id"].startswith("ig-media-"), doc["ig_media_id"]
	assert doc["published_at"] is not None

	# --- list + status filter ---
	app.ingest_batch(source="s", run_date="2026-06-20", carousels=PAYLOAD)  # a second, still pending
	assert len(store.list(None, 50, 0)) == 2
	assert {d["status"] for d in store.list("published", 50, 0)} == {"published"}
	assert len(store.list("pending", 50, 0)) == 1

	# --- render failure path ---
	rid = app.ingest_batch(source="s", run_date="2026-06-20", carousels=PAYLOAD)["carousel_ids"][0]

	class Boom:
		def render(self, *a, **k):
			raise RuntimeError("render exploded")

	try:
		run_render(app, UUID(rid), Boom())
	except RuntimeError:
		pass
	else:  # pragma: no cover
		raise AssertionError("expected render failure to propagate")
	failed = store.get(rid)
	assert failed["status"] == "failed" and "exploded" in failed["error"], failed

	# --- approve guard: cannot approve a pending carousel ---
	try:
		app.approve(UUID(rid))
	except CommandError as exc:
		assert "not ready" in str(exc), exc
	else:  # pragma: no cover
		raise AssertionError("expected approve guard")

	print("OK — ingest -> async render -> ready -> approve -> publish + failure paths verified")


if __name__ == "__main__":
	main()
