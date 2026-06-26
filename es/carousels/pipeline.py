"""Side-effecting workers + ports for the carousel pipeline.

Rendering (slow, external: WeasyPrint + ImageKit) and publishing (Meta Graph
API) are kept OUT of aggregates and projections. They run here as workers that
perform the effect and then feed the result back as events via the application.

Ports are injectable so tests use fakes and never touch WeasyPrint/ImageKit/Meta.
The production adapters live in es/carousels/adapters.py (RealRenderer / RealPublisher).
"""
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from .application import Carousels


class SlideRenderer(Protocol):
	def render(
		self,
		slide: dict,
		*,
		carousel_id: str,
		order: int,
		total: int,
		category: str,
		credibility: float,
	) -> tuple[str, str]:
		"""Return (image_url, file_id)."""
		...


class Publisher(Protocol):
	def publish(self, *, carousel: dict, caption: str) -> tuple[str, str]:
		"""Return (ig_media_id, ig_container_id)."""
		...


class LocalRenderer:
	"""Deterministic placeholder — no external deps. Dev/test default.

	Production: implement SlideRenderer over carousels.renderer.render_slide_png
	+ carousels.storage.upload_png.
	"""

	def render(self, slide, *, carousel_id, order, total, category, credibility):
		return f"local://carousels/{carousel_id}_slide_{order:02d}.png", f"local-{order:02d}"


class FakePublisher:
	def publish(self, *, carousel, caption):
		return f"ig-media-{carousel['id'][:8]}", f"ig-container-{carousel['id'][:8]}"


def run_render(app: Carousels, carousel_id: UUID, renderer: SlideRenderer) -> None:
	"""Worker body — render every slide, feed results back as events.

	This is what the Celery task calls. On failure records RenderFailed and
	re-raises so the task can retry. Idempotent enough: re-running re-renders
	and re-applies SlideRendered (last write wins).
	"""
	carousel = app.get(carousel_id)
	total = len(carousel.slides)
	try:
		for s in carousel.slides:
			image_url, file_id = renderer.render(
				s["payload"],
				carousel_id=str(carousel_id),
				order=s["order"],
				total=total,
				category=carousel.category,
				credibility=carousel.credibility,
			)
			app.slide_rendered(carousel_id, s["order"], image_url, file_id)
		app.complete_render(carousel_id)
	except Exception as exc:
		app.fail_render(carousel_id, str(exc))
		raise


def default_caption(doc: dict) -> str:
	cat = doc.get("category", "")
	tags = " ".join(f"#{t.replace(' ', '')}" for t in (cat, "news") if t)
	sources = ", ".join(doc.get("sources", []))
	return f"{doc['headline']}\n\n{doc.get('summary', '')}\n\nSources: {sources}\n\n{tags}"


def publish_carousel(app: Carousels, publisher: Publisher, carousel_id: UUID, doc: dict, caption: str):
	"""Synchronous publish (mirrors legacy): call Meta, then record the event."""
	media_id, container_id = publisher.publish(carousel=doc, caption=caption)
	published_at = datetime.now(timezone.utc).isoformat()
	return app.mark_published(carousel_id, media_id, container_id, published_at)
