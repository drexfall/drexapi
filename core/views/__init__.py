from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import render


def index(request):
	view_context = {
		"title": "Welcome to drexFall"
	}
	return render(request, 'core/index.html', view_context)


def spa(request, **kwargs):
	html_file = Path(settings.BASE_DIR) / "static" / "dist" / "index.html"
	if not html_file.exists():
		raise Http404("Frontend not built. Run: cd frontend && npm run build")
	return HttpResponse(html_file.read_text(), content_type="text/html")
