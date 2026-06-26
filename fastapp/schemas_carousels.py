from datetime import date

from pydantic import BaseModel, Field


class IngestSlide(BaseModel):
	type: str
	model_config = {"extra": "allow"}  # remaining fields are free-form per slide type


class IngestCarousel(BaseModel):
	story_index: int = 0
	headline: str = Field(max_length=512)
	summary: str = ""
	category: str = "other"
	sources: list[str] = Field(default_factory=list)
	credibility: float = 0.0
	url: str = ""
	slides: list[IngestSlide]


class IngestPayload(BaseModel):
	source: str = "newsscraper"
	run_date: date
	carousels: list[IngestCarousel]


class IngestResult(BaseModel):
	batch_id: str
	carousel_ids: list[str]


class SlideOut(BaseModel):
	order: int
	slide_type: str
	payload: dict
	image_url: str


class CarouselListItem(BaseModel):
	id: str
	headline: str
	category: str
	credibility: float
	status: str
	created_at: str
	published_at: str | None = None


class CarouselDetail(BaseModel):
	id: str
	batch_id: str
	story_index: int
	headline: str
	summary: str
	category: str
	sources: list[str]
	credibility: float
	url: str
	status: str
	error: str
	ig_media_id: str
	ig_container_id: str
	published_at: str | None = None
	slides: list[SlideOut]
	created_at: str
	updated_at: str


class PublishRequest(BaseModel):
	caption: str | None = None
