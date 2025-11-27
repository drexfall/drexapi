from django.shortcuts import render
from pydparser import ResumeParser
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FileUploadParser, MultiPartParser, FormParser
from rest_framework.response import Response


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def read(request):
	data = []
	for pdf_name in request.data:
		pdf_data = request.data[pdf_name]
		file = pdf_data.open()
		with open(pdf_name + ".pdf", "wb") as f:
			f.write(file.read())
		data.append(ResumeParser(pdf_name + ".pdf").get_extracted_data())

	return Response({"data": data})


def index(request):
	return render(request, "api/parser.html")
