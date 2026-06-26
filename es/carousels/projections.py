"""Read side — projects Carousel events into the carousel read model.

Pure + idempotent: no rendering/publishing side-effects here (those run in
pipeline.py workers and feed back as events). This only shapes query docs.
"""
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication

from . import readmodel
from .domain import Carousel, normalize_slides


def _slide_view(s: dict) -> dict:
	return {
		"order": s["order"],
		"slide_type": s["slide_type"],
		"payload": s["payload"],
		"image_url": s["image_url"],
	}


class CarouselReadModel(ProcessApplication):
	@singledispatchmethod
	def policy(self, domain_event, processing_event):
		"""Default: ignore."""

	@policy.register
	def _ingested(self, domain_event: Carousel.Ingested, processing_event):
		ts = domain_event.timestamp.isoformat()
		readmodel.get_carousel_store().upsert(
			{
				"id": str(domain_event.originator_id),
				"batch_id": domain_event.batch_id,
				"story_index": domain_event.story_index,
				"headline": domain_event.headline,
				"summary": domain_event.summary,
				"category": domain_event.category,
				"sources": domain_event.sources,
				"credibility": domain_event.credibility,
				"url": domain_event.url,
				"status": Carousel.PENDING,
				"error": "",
				"ig_media_id": "",
				"ig_container_id": "",
				"published_at": None,
				"slides": [_slide_view(s) for s in normalize_slides(domain_event.slides)],
				"created_at": ts,
				"updated_at": ts,
			}
		)

	@policy.register
	def _slide_rendered(self, domain_event: Carousel.SlideRendered, processing_event):
		readmodel.get_carousel_store().set_slide_image(
			str(domain_event.originator_id),
			domain_event.order,
			domain_event.image_url,
			domain_event.file_id,
		)

	@policy.register
	def _completed(self, domain_event: Carousel.RenderCompleted, processing_event):
		readmodel.get_carousel_store().patch(
			str(domain_event.originator_id),
			{"status": Carousel.READY, "error": "", "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _render_failed(self, domain_event: Carousel.RenderFailed, processing_event):
		readmodel.get_carousel_store().patch(
			str(domain_event.originator_id),
			{"status": Carousel.FAILED, "error": domain_event.error, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _approved(self, domain_event: Carousel.Approved, processing_event):
		readmodel.get_carousel_store().patch(
			str(domain_event.originator_id),
			{"status": Carousel.APPROVED, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _published(self, domain_event: Carousel.Published, processing_event):
		readmodel.get_carousel_store().patch(
			str(domain_event.originator_id),
			{
				"status": Carousel.PUBLISHED,
				"ig_media_id": domain_event.ig_media_id,
				"ig_container_id": domain_event.ig_container_id,
				"published_at": domain_event.published_at,
				"error": "",
				"updated_at": domain_event.timestamp.isoformat(),
			},
		)

	@policy.register
	def _publish_failed(self, domain_event: Carousel.PublishFailed, processing_event):
		readmodel.get_carousel_store().patch(
			str(domain_event.originator_id),
			{"error": domain_event.error, "updated_at": domain_event.timestamp.isoformat()},
		)
