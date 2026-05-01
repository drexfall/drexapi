# Create your views here.

from django.conf import settings
from django.core.mail import EmailMessage
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from submit.forms import *


@api_view(['GET'])
def form(request, portal_name, form_name):
	if portal_name == 'umalang' and form_name == 'contact':
		contact_form = UMalangContactForm()
		return Response({"form": contact_form.as_div()}, status=status.HTTP_200_OK)
	return Response({"message": "Cannot find form"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def submit(request):
	name = request.POST.get('name')
	message = request.POST.get('message')
	email = request.POST.get('reply_email')
	receiver_email = 'shreyashsingh477@gmail.com'

	error = []
	if not name:
		error.append("Name is required.")
	if not message:
		error.append("Message is required.")
	if not email:
		error.append("Email is required.")
	if not receiver_email:
		error.append("Email is required.")

	if error:
		return Response({"errors": error}, status=status.HTTP_400_BAD_REQUEST)
	# Get the email template
	html_content = render(
		request,
		"core/email/umalang.html",
		{"name": name, "message": message, "email": email})

	# Generate the email object
	email_obj = EmailMessage(
		subject="New Message on UMalang Portal",
		from_email=settings.SENDER_EMAIL,
		to=[receiver_email],
		reply_to=[email],
	)
	email_obj.content_subtype = "html"
	email_obj.body = html_content.content.decode("utf-8")

	# Try sending the email
	try:
		email_obj.send()
		return Response({'message': "Email sent successfully"}, status=status.HTTP_200_OK)
	except Exception as e:
		return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
