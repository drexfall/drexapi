import os

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from drexfall.settings import imagekit

URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT")

@api_view(['GET'])
def get(request, image_id):
    file = request.data['file']
    filename = request.data['name']


@api_view(['POST'])
def upload(request):
    file = request.data['file']
    filename = request.data['name']

    try:
        result = imagekit.files.upload(file=file,
                                      file_name=filename)
        return Response({"url": result.url, "id": result.id, "status": status.HTTP_200_OK})
    except Exception as e:

        return Response({"message": e, "status": status.HTTP_400_BAD_REQUEST})
