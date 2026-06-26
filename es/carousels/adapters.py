"""Production adapters for the carousel pipeline ports.

De-Djangoed from the former carousels/storage.py + carousels/publish.py. Rendering
runs via es/carousels/render_impl.py (a de-Djangoed copy of the old renderer):
pure Jinja2 -> WeasyPrint -> pypdfium, no Django.

Selected by env via default_renderer()/default_publisher():
  - CAROUSEL_REAL_RENDER=true              -> RealRenderer (else LocalRenderer)
  - META_ACCESS_TOKEN + META_IG_USER_ID    -> RealPublisher (else FakePublisher)
"""
import base64
import logging
import time
from pathlib import Path

import requests

from es.config import Settings, get_settings

from .pipeline import FakePublisher, LocalRenderer, Publisher, SlideRenderer

log = logging.getLogger(__name__)


class PublishError(RuntimeError):
	pass


# --- storage (ImageKit + local fallback) ---


class ImageKitStorage:
	def __init__(self, settings: Settings) -> None:
		self._ik = None
		if settings.imagekit_private and settings.imagekit_public and settings.imagekit_url_endpoint:
			from imagekitio import ImageKit

			self._ik = ImageKit(
				private_key=settings.imagekit_private,
				public_key=settings.imagekit_public,
				url_endpoint=settings.imagekit_url_endpoint,
			)
		self._media_root = Path(settings.media_root)
		self._media_url = settings.media_url

	def upload(self, png: bytes, *, filename: str, folder: str = "/carousels") -> tuple[str, str]:
		if self._ik is not None:
			try:
				res = self._ik.upload_file(
					file=base64.b64encode(png).decode(),
					file_name=filename,
					options={"folder": folder, "use_unique_file_name": True},
				)
				url = getattr(res, "url", None) or res["url"]
				fid = getattr(res, "file_id", None) or res.get("file_id", "")
				return url, fid
			except Exception:
				log.exception("imagekit upload failed, falling back to local media")

		out_dir = self._media_root / folder.strip("/")
		out_dir.mkdir(parents=True, exist_ok=True)
		(out_dir / filename).write_bytes(png)
		return f"{self._media_url}{folder.strip('/')}/{filename}", ""


# --- renderer (Jinja2 -> WeasyPrint -> pypdfium PNG, then upload) ---


class RealRenderer:
	def __init__(self, storage: ImageKitStorage) -> None:
		self._storage = storage

	def render(self, slide, *, carousel_id, order, total, category, credibility):
		from .render_impl import render_slide_png  # de-Djangoed local copy

		png = render_slide_png(
			slide, order=order, total=total, category=category, credibility=credibility
		)
		return self._storage.upload(png, filename=f"{carousel_id}_slide_{order:02d}.png")


# --- publisher (Meta Graph API) ---


class RealPublisher:
	def __init__(self, settings: Settings) -> None:
		self._ig_user = settings.meta_ig_user_id
		self._token = settings.meta_access_token
		self._version = settings.meta_graph_version

	def _api(self, path: str, *, params=None, method: str = "POST") -> dict:
		if not self._token:
			raise PublishError("META_ACCESS_TOKEN not set")
		url = f"https://graph.facebook.com/{self._version}/{path.lstrip('/')}"
		payload = dict(params or {})
		payload["access_token"] = self._token
		if method == "GET":
			r = requests.get(url, params=payload, timeout=30)
		else:
			r = requests.post(url, data=payload, timeout=60)
		if not r.ok:
			raise PublishError(f"meta api {r.status_code}: {r.text}")
		return r.json()

	def _wait_container_ready(self, creation_id: str, *, max_wait_s: int = 60) -> None:
		deadline = time.time() + max_wait_s
		while time.time() < deadline:
			data = self._api(creation_id, params={"fields": "status_code"}, method="GET")
			code = data.get("status_code")
			if code == "FINISHED":
				return
			if code == "ERROR":
				raise PublishError(f"container {creation_id} errored")
			time.sleep(2)
		raise PublishError(f"container {creation_id} timeout")

	def publish(self, *, carousel: dict, caption: str) -> tuple[str, str]:
		if not self._ig_user:
			raise PublishError("META_IG_USER_ID not set")
		slides = sorted(carousel.get("slides", []), key=lambda s: s["order"])
		if not slides:
			raise PublishError("carousel has no slides")
		missing = [s["order"] for s in slides if not s.get("image_url")]
		if missing:
			raise PublishError(f"slides missing image_url: {missing}")

		child_ids: list[str] = []
		for s in slides:
			res = self._api(
				f"{self._ig_user}/media",
				params={"image_url": s["image_url"], "is_carousel_item": "true"},
			)
			cid = res.get("id")
			if not cid:
				raise PublishError(f"no creation id for slide {s['order']}: {res}")
			child_ids.append(cid)

		carousel_res = self._api(
			f"{self._ig_user}/media",
			params={"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
		)
		container_id = carousel_res.get("id")
		if not container_id:
			raise PublishError(f"no carousel creation id: {carousel_res}")

		self._wait_container_ready(container_id)

		publish_res = self._api(f"{self._ig_user}/media_publish", params={"creation_id": container_id})
		media_id = publish_res.get("id")
		if not media_id:
			raise PublishError(f"publish returned no id: {publish_res}")
		# (ig_media_id, ig_container_id) — matches pipeline.publish_carousel contract
		return media_id, container_id


# --- env-driven selection ---


def default_renderer(settings: Settings | None = None) -> SlideRenderer:
	settings = settings or get_settings()
	if settings.carousel_real_render:
		return RealRenderer(ImageKitStorage(settings))
	return LocalRenderer()


def default_publisher(settings: Settings | None = None) -> Publisher:
	settings = settings or get_settings()
	if settings.meta_access_token and settings.meta_ig_user_id:
		return RealPublisher(settings)
	return FakePublisher()
