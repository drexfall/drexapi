from django.shortcuts import redirect
from django_hosts.resolvers import reverse


# Create your views here.
def index(request, code_id=None):
	if code_id == "762egk3t":
		return redirect(reverse('index', host="profiles", kwargs={"profile_id": "drprakash"}))

	return redirect(reverse('index', host="core"))
	# return render(request, 'scan/index.html')
