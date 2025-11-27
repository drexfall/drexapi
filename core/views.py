from django.shortcuts import render


# Create your views here.

def index(request):
	view_context = {
		"title": "Welcome to drexFall"
	}
	return render(request, 'core/index.html', view_context)
