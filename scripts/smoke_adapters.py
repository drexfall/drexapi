"""Smoke test for slice 4b — real carousel adapters.

No WeasyPrint (render fn monkeypatched), no ImageKit (local fallback), no Meta
(HTTP monkeypatched). Verifies storage fallback, RealRenderer wiring, the full
RealPublisher Graph-API flow, and env-driven adapter selection.

Run: PYTHONPATH=. .venv/bin/python scripts/smoke_adapters.py
"""
import tempfile
import types
from pathlib import Path

from es.carousels import adapters
from es.carousels.adapters import (
	FakePublisher,
	ImageKitStorage,
	LocalRenderer,
	RealPublisher,
	RealRenderer,
	default_publisher,
	default_renderer,
)
from es.config import Settings


def test_storage_local_fallback() -> None:
	tmp = tempfile.mkdtemp()
	st = Settings(
		imagekit_private="", imagekit_public="", imagekit_url_endpoint="",
		media_root=tmp, media_url="/media/",
	)
	store = ImageKitStorage(st)
	url, fid = store.upload(b"PNGBYTES", filename="abc_slide_00.png")
	assert url == "/media/carousels/abc_slide_00.png", url
	assert fid == ""
	assert (Path(tmp) / "carousels" / "abc_slide_00.png").read_bytes() == b"PNGBYTES"
	print("  storage local fallback OK")


def test_real_renderer(monkeypatch_target) -> None:
	# avoid WeasyPrint: stub the pure render fn that RealRenderer imports
	import es.carousels.render_impl as render_impl

	render_impl.render_slide_png = lambda slide, **kw: b"FAKEPNG"  # type: ignore

	tmp = tempfile.mkdtemp()
	st = Settings(imagekit_private="", media_root=tmp, media_url="/media/")
	r = RealRenderer(ImageKitStorage(st))
	url, fid = r.render({"type": "cover"}, carousel_id="C1", order=2, total=3, category="tech", credibility=0.5)
	assert url == "/media/carousels/C1_slide_02.png", url
	assert (Path(tmp) / "carousels" / "C1_slide_02.png").read_bytes() == b"FAKEPNG"
	print("  RealRenderer -> storage OK")


def test_real_publisher() -> None:
	calls = []

	class Resp:
		def __init__(self, payload):
			self._p = payload
			self.ok = True
			self.status_code = 200
			self.text = str(payload)

		def json(self):
			return self._p

	def fake_post(url, data=None, timeout=None):
		calls.append(("POST", url))
		if url.endswith("/media") and data.get("is_carousel_item") == "true":
			return Resp({"id": f"child{len([c for c in calls if c[1].endswith('/media')])}"})
		if url.endswith("/media") and data.get("media_type") == "CAROUSEL":
			assert "child" in data["children"], data["children"]
			return Resp({"id": "container-1"})
		if url.endswith("/media_publish"):
			assert data["creation_id"] == "container-1"
			return Resp({"id": "media-999"})
		raise AssertionError(f"unexpected POST {url} {data}")

	def fake_get(url, params=None, timeout=None):
		calls.append(("GET", url))
		return Resp({"status_code": "FINISHED"})

	adapters.requests = types.SimpleNamespace(post=fake_post, get=fake_get)

	pub = RealPublisher(Settings(meta_ig_user_id="ig-1", meta_access_token="tok", meta_graph_version="v23.0"))
	doc = {
		"id": "C1",
		"slides": [
			{"order": 1, "image_url": "http://img/1.png"},
			{"order": 0, "image_url": "http://img/0.png"},
		],
	}
	media_id, container_id = pub.publish(carousel=doc, caption="hi")
	assert media_id == "media-999", media_id
	assert container_id == "container-1", container_id
	# 2 child creates + 1 carousel create + 1 status poll + 1 publish
	assert [c[0] for c in calls] == ["POST", "POST", "POST", "GET", "POST"], calls
	print("  RealPublisher Graph-API flow OK")


def test_missing_image_url_rejected() -> None:
	pub = RealPublisher(Settings(meta_ig_user_id="ig-1", meta_access_token="tok"))
	try:
		pub.publish(carousel={"id": "C", "slides": [{"order": 0, "image_url": ""}]}, caption="x")
	except adapters.PublishError as exc:
		assert "missing image_url" in str(exc), exc
	else:
		raise AssertionError("expected PublishError")
	print("  publish rejects unrendered slides OK")


def test_env_selection() -> None:
	assert isinstance(default_renderer(Settings(carousel_real_render=False)), LocalRenderer)
	assert isinstance(default_renderer(Settings(carousel_real_render=True)), RealRenderer)
	assert isinstance(default_publisher(Settings()), FakePublisher)
	assert isinstance(
		default_publisher(Settings(meta_ig_user_id="u", meta_access_token="t")), RealPublisher
	)
	print("  env-driven adapter selection OK")


def main() -> None:
	test_storage_local_fallback()
	test_real_renderer(None)
	test_real_publisher()
	test_missing_image_url_rejected()
	test_env_selection()
	print("OK — real render/storage/publish adapters verified")


if __name__ == "__main__":
	main()
