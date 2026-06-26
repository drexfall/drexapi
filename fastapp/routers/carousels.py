import hmac
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status

from es.application import CommandError
from es.carousels.adapters import default_publisher, default_renderer
from es.carousels.application import CarouselNotFound, Carousels
from es.carousels.pipeline import (
	Publisher,
	SlideRenderer,
	default_caption,
	publish_carousel,
	run_render,
)
from es.carousels.readmodel import get_carousel_store
from es.carousels.system import get_carousels_app
from es.config import Settings, get_settings
from fastapp.auth import Principal, require_principal
from fastapp.schemas_carousels import (
	CarouselDetail,
	CarouselListItem,
	IngestPayload,
	IngestResult,
	PublishRequest,
)

router = APIRouter(tags=["carousels"])

# Injectable adapters — env-selected (real WeasyPrint/ImageKit/Meta when configured,
# else placeholder LocalRenderer / FakePublisher). Override in tests via setters.
_renderer: SlideRenderer = default_renderer()
_publisher: Publisher = default_publisher()


def set_renderer(r: SlideRenderer) -> None:
	global _renderer
	_renderer = r


def set_publisher(p: Publisher) -> None:
	global _publisher
	_publisher = p


def _app() -> Carousels:
	return get_carousels_app()


def require_ingest_token(
	authorization: str | None = Header(default=None),
	settings: Settings = Depends(get_settings),
) -> None:
	if not settings.carousel_ingest_token:
		raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ingest token not configured")
	parts = (authorization or "").split()
	if len(parts) != 2 or parts[0].lower() != "bearer":
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
	if not hmac.compare_digest(parts[1], settings.carousel_ingest_token):
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid ingest token")


@router.post(
	"/carousels/ingest",
	response_model=IngestResult,
	status_code=status.HTTP_201_CREATED,
	dependencies=[Depends(require_ingest_token)],
)
def ingest(payload: IngestPayload, bg: BackgroundTasks, app: Carousels = Depends(_app)):
	result = app.ingest_batch(
		source=payload.source,
		run_date=str(payload.run_date),
		carousels=[c.model_dump() for c in payload.carousels],
	)
	# enqueue render per carousel. Prod: swap BackgroundTasks for a Celery .delay().
	for cid in result["carousel_ids"]:
		bg.add_task(run_render, app, UUID(cid), _renderer)
	return IngestResult(batch_id=result["batch_id"], carousel_ids=result["carousel_ids"])


@router.get("/carousels", response_model=list[CarouselListItem])
def list_carousels(
	principal: Principal = Depends(require_principal),
	status_filter: str | None = Query(default=None, alias="status"),
	limit: int = Query(default=50, ge=1, le=500),
	skip: int = Query(default=0, ge=0),
):
	return get_carousel_store().list(status_filter, limit=limit, skip=skip)


@router.get("/carousels/{cid}", response_model=CarouselDetail)
def get_carousel(cid: UUID, principal: Principal = Depends(require_principal)):
	doc = get_carousel_store().get(str(cid))
	if doc is None:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Carousel not found")
	return doc


@router.post("/carousels/{cid}/approve", response_model=CarouselDetail)
def approve_carousel(
	cid: UUID, principal: Principal = Depends(require_principal), app: Carousels = Depends(_app)
):
	try:
		app.approve(cid)
	except CarouselNotFound:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Carousel not found")
	except CommandError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
	return get_carousel_store().get(str(cid))


@router.post("/carousels/{cid}/publish", response_model=CarouselDetail)
def publish(
	cid: UUID,
	body: PublishRequest,
	principal: Principal = Depends(require_principal),
	app: Carousels = Depends(_app),
):
	try:
		app.assert_publishable(cid)
	except CarouselNotFound:
		raise HTTPException(status.HTTP_404_NOT_FOUND, "Carousel not found")
	except CommandError as exc:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

	doc = get_carousel_store().get(str(cid))
	caption = body.caption or default_caption(doc)
	try:
		publish_carousel(app, _publisher, cid, doc, caption)
	except Exception as exc:  # external Meta API failure
		app.fail_publish(cid, str(exc))
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
	return get_carousel_store().get(str(cid))
