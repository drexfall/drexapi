from django.shortcuts import render

from core.views import index as core_index


# Create your views here.
def index(request, profile_id=None):
	if profile_id == "drprakash":
		return render(request, 'profiles/index.html', {"title": 'Dr. Prakash\'s Profile - drexfall'})
	return core_index(request)
	# return render(request, 'profiles/index.html')
