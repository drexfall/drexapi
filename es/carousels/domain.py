"""Write model — the Carousel aggregate.

Mirrors legacy carousels.models.Carousel + Slide and its status machine:
pending -> ready -> approved -> published (or failed). Render results and the
publish outcome arrive as events fed back by out-of-band workers (pipeline.py),
so the aggregate stays the single source of truth and projections stay pure.
"""
from eventsourcing.domain import Aggregate, event


def normalize_slides(raw: list[dict]) -> list[dict]:
	"""Input slide dicts -> stored slide shape. Deterministic (re-run on replay)."""
	return [
		{
			"order": i,
			"slide_type": s.get("type", "narrative"),
			"payload": s,
			"image_url": "",
			"file_id": "",
		}
		for i, s in enumerate(raw)
	]


class Carousel(Aggregate):
	PENDING = "pending"
	READY = "ready"
	APPROVED = "approved"
	PUBLISHED = "published"
	FAILED = "failed"

	@event("Ingested")
	def __init__(
		self,
		batch_id: str,
		story_index: int,
		headline: str,
		summary: str,
		category: str,
		sources: list,
		credibility: float,
		url: str,
		slides: list,
	):
		self.batch_id = batch_id
		self.story_index = story_index
		self.headline = headline
		self.summary = summary
		self.category = category
		self.sources = sources
		self.credibility = credibility
		self.url = url
		self.slides = normalize_slides(slides)
		self.status = self.PENDING
		self.error = ""
		self.ig_media_id = ""
		self.ig_container_id = ""
		self.published_at = None

	# --- render (driven by the async worker) ---

	@event("SlideRendered")
	def slide_rendered(self, order: int, image_url: str, file_id: str) -> None:
		for s in self.slides:
			if s["order"] == order:
				s["image_url"] = image_url
				s["file_id"] = file_id

	@event("RenderCompleted")
	def complete_render(self) -> None:
		self.status = self.READY
		self.error = ""

	@event("RenderFailed")
	def fail_render(self, error: str) -> None:
		self.status = self.FAILED
		self.error = error

	# --- review / publish ---

	@event("Approved")
	def approve(self) -> None:
		self.status = self.APPROVED

	@event("Published")
	def mark_published(self, ig_media_id: str, ig_container_id: str, published_at: str) -> None:
		self.status = self.PUBLISHED
		self.ig_media_id = ig_media_id
		self.ig_container_id = ig_container_id
		self.published_at = published_at
		self.error = ""

	@event("PublishFailed")
	def fail_publish(self, error: str) -> None:
		self.error = error
