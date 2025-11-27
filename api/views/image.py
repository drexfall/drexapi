from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from drexfall.settings import imagekit

options = UploadFileRequestOptions(
	use_unique_file_name=False,
	folder='UMalang',
	overwrite_file=True,
)


@api_view(['GET'])
def get(request, image_id):
	file = request.data['file']
	filename = request.data['name']


@api_view(['POST'])
def upload(request):
	file = request.data['file']
	filename = request.data['name']

	try:
		result = imagekit.upload_file(file=file,
		                              file_name=filename,
		                              options=options)
		return Response({"url": result.url, "id": result.id, "status": status.HTTP_200_OK})
	except Exception as e:

		return Response({"message": e, "status": status.HTTP_400_BAD_REQUEST})
