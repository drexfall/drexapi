from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Portal


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save(request, portal_name):
	content = request.data['content']

	portal = get_portal(portal_name)
	if type(portal) is not Portal:
		return portal
	portal.content = content
	portal.save()
	return Response({"message": f"Database {portal.name} saved successfully"}, status=status.HTTP_200_OK)


@api_view(['GET'])
def read(request, portal_name):
	portal = get_portal(portal_name)
	if type(portal) is not Portal:
		return portal
	return Response(portal.content, status=status.HTTP_200_OK)


def get_portal(portal_name):
	try:
		return Portal.objects.get(name=portal_name)
	except Portal.DoesNotExist as e:
		return Response({"message": f"Database {portal_name} does not exist"}, status=status.HTTP_404_NOT_FOUND)
