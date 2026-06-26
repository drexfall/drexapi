"""Application service for carousels — command side."""
from uuid import UUID, uuid4

from eventsourcing.application import Application

from es.application import CommandError, ProjectNotFound  # reuse error types

from .domain import Carousel


class CarouselNotFound(ProjectNotFound):
	pass


class Carousels(Application):
	def ingest_batch(self, *, source: str, run_date: str, carousels: list[dict]) -> dict:
		batch_id = uuid4().hex
		ids = []
		for c in carousels:
			ids.append(str(self._ingest_one(batch_id, c)))
		return {"batch_id": batch_id, "source": source, "run_date": run_date, "carousel_ids": ids}

	def _ingest_one(self, batch_id: str, c: dict) -> UUID:
		carousel = Carousel(
			batch_id=batch_id,
			story_index=c.get("story_index", 0),
			headline=c["headline"],
			summary=c.get("summary", ""),
			category=c.get("category", "other"),
			sources=c.get("sources", []),
			credibility=c.get("credibility", 0.0),
			url=c.get("url", ""),
			slides=c["slides"],
		)
		self.save(carousel)
		return carousel.id

	def get(self, cid: UUID) -> Carousel:
		try:
			return self.repository.get(cid)
		except Exception as exc:
			raise CarouselNotFound(str(cid)) from exc

	# --- render results (from worker) ---

	def slide_rendered(self, cid: UUID, order: int, image_url: str, file_id: str) -> None:
		carousel = self.get(cid)
		carousel.slide_rendered(order, image_url, file_id)
		self.save(carousel)

	def complete_render(self, cid: UUID) -> None:
		carousel = self.get(cid)
		carousel.complete_render()
		self.save(carousel)

	def fail_render(self, cid: UUID, error: str) -> None:
		carousel = self.get(cid)
		carousel.fail_render(error)
		self.save(carousel)

	# --- review / publish ---

	def approve(self, cid: UUID) -> Carousel:
		carousel = self.get(cid)
		if carousel.status != Carousel.READY:
			raise CommandError(f"carousel not ready (status={carousel.status})")
		carousel.approve()
		self.save(carousel)
		return carousel

	def mark_published(self, cid: UUID, ig_media_id: str, ig_container_id: str, published_at: str) -> Carousel:
		carousel = self.get(cid)
		carousel.mark_published(ig_media_id, ig_container_id, published_at)
		self.save(carousel)
		return carousel

	def fail_publish(self, cid: UUID, error: str) -> None:
		carousel = self.get(cid)
		carousel.fail_publish(error)
		self.save(carousel)

	def assert_publishable(self, cid: UUID) -> Carousel:
		carousel = self.get(cid)
		if carousel.status not in (Carousel.APPROVED, Carousel.READY):
			raise CommandError(f"not publishable (status={carousel.status})")
		return carousel
