"""Render carousel slides to PNG via Jinja2 -> WeasyPrint(PDF) -> pypdfium2(PNG).

Public entrypoint: render_slide_png(slide_payload, ctx) -> bytes (PNG).
"""
import io
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .theme import DEFAULT_THEME, category_color

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "carousels"


def _env() -> Environment:
	return Environment(
		loader=FileSystemLoader(str(_TEMPLATE_DIR)),
		autoescape=select_autoescape(["html"]),
	)


def render_slide_html(slide: dict, *, order: int, total: int, category: str, credibility: float) -> str:
	tpl = _env().get_template("slide.html")
	return tpl.render(
		slide=slide,
		order=order,
		total=total,
		category=category or "other",
		credibility=credibility,
		theme=DEFAULT_THEME,
		category_color=category_color(category),
	)


def html_to_png(html: str, *, width_px: int = 1080) -> bytes:
	"""HTML -> PDF (WeasyPrint) -> PNG (pypdfium2). Returns raw PNG bytes."""
	# Imported lazily to keep import-time light and avoid hard dep at import.
	from weasyprint import HTML  # type: ignore
	import pypdfium2 as pdfium  # type: ignore

	pdf_bytes = HTML(string=html, base_url=str(_TEMPLATE_DIR)).write_pdf()
	pdf = pdfium.PdfDocument(pdf_bytes)
	page = pdf[0]
	# Page is 1080px wide at 96 DPI. Scale to target width.
	scale = width_px / page.get_width()
	pil_image = page.render(scale=scale).to_pil()
	buf = io.BytesIO()
	pil_image.save(buf, format="PNG", optimize=True)
	return buf.getvalue()


def render_slide_png(slide: dict, *, order: int, total: int, category: str, credibility: float) -> bytes:
	html = render_slide_html(
		slide,
		order=order,
		total=total,
		category=category,
		credibility=credibility,
	)
	return html_to_png(html)
