from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.mail import EmailMessage


# Create your views here.
def read_database():
	# with open('daabase.json', 'r') as f:
	#     return json.load(f)
	return {
		"bananaTypes": ["Apple Banana", "Cavendish", "Lady Finger", "Red Dacca"],
		"availableStock": [100, 200, 300, 400]
	}


@api_view(['GET', 'POST'])
def index(request):
	print(request.POST)

	try:
		email = EmailMessage(
			subject=request.POST.get("subject"),
			body=request.POST.get("message"),
			from_email='admin@drexfall.com',
			to=['shreyashsingh477@gmail.com'],
			reply_to=[request.POST.get("reply_email")],
			headers={'Content-Type': 'text/plain'},
		)
		email.send()
		return Response({'error': False, 'message': "Email sent successfully"}, status=200)
	except Exception as e:
		return Response({'error': True, 'message': str(e)}, status=500)
