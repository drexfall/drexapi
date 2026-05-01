from django.contrib.auth import get_user_model
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Membership, Role
from accounts.permissions import HasProjectRole
from projects import commands, queries
from projects.models import Project
from projects.mongo import MongoConnector
from projects.serializers import (
	DocumentSerializer,
	MembershipReadSerializer,
	MembershipWriteSerializer,
	ProjectPatchSerializer,
	ProjectSerializer,
	ProjectWriteSerializer,
)

User = get_user_model()


class ProjectViewSet(viewsets.ViewSet):
	permission_classes = [IsAuthenticated, HasProjectRole]
	lookup_field = "pk"
	required_role = Role.ADMIN
	read_role = Role.VIEWER

	def get_permissions(self):
		if self.action in ("list", "create"):
			return [IsAuthenticated()]
		return super().get_permissions()

	def _get_object(self, pk) -> Project:
		project = queries.get_project_or_404(pk)
		self.check_object_permissions(self.request, project)
		return project

	def list(self, request):
		qs = queries.list_projects_for_user(request.user)
		page = qs[:100]
		return Response(ProjectSerializer(page, many=True).data)

	def create(self, request):
		s = ProjectWriteSerializer(data=request.data)
		s.is_valid(raise_exception=True)
		project = commands.create_project(owner=request.user, **s.validated_data)
		return Response(ProjectSerializer(project).data, status=status.HTTP_202_ACCEPTED)

	def retrieve(self, request, pk=None):
		project = self._get_object(pk)
		return Response(queries.read_project_view(project))

	def partial_update(self, request, pk=None):
		self.required_role = Role.EDITOR
		project = self._get_object(pk)
		s = ProjectPatchSerializer(data=request.data, partial=True)
		s.is_valid(raise_exception=True)
		project = commands.update_project(project, changes=s.validated_data)
		return Response(ProjectSerializer(project).data)

	def destroy(self, request, pk=None):
		self.required_role = Role.ADMIN
		project = self._get_object(pk)
		commands.delete_project(project)
		return Response(status=status.HTTP_204_NO_CONTENT)

	@action(detail=True, methods=["get"], url_path="documents")
	def list_documents(self, request, pk=None):
		self.required_role = Role.VIEWER
		project = self._get_object(pk)
		limit = min(int(request.query_params.get("limit", 50)), 500)
		skip = max(int(request.query_params.get("skip", 0)), 0)
		return Response(queries.list_documents(project, limit=limit, skip=skip))

	@action(detail=True, methods=["post"], url_path="documents")
	def create_document(self, request, pk=None):
		self.required_role = Role.EDITOR
		project = self._get_object(pk)
		s = DocumentSerializer(data=request.data)
		s.is_valid(raise_exception=True)
		from django.utils import timezone
		doc = {
			"doc_type": "document",
			"data": s.validated_data["data"],
			"created_by": request.user.pk,
			"created_at": timezone.now(),
		}
		coll = MongoConnector().project_collection(project.id)
		result = coll.insert_one(doc)
		doc["_id"] = str(result.inserted_id)
		return Response(doc, status=status.HTTP_201_CREATED)

	@action(detail=True, methods=["get", "post"], url_path="members")
	def members(self, request, pk=None):
		project = self._get_object(pk)
		if request.method == "GET":
			self.required_role = Role.VIEWER
			qs = Membership.objects.filter(project=project).select_related("user")
			data = [
				{
					"user_id": m.user_id,
					"username": m.user.username,
					"email": m.user.email,
					"role": m.role,
				}
				for m in qs
			]
			return Response(data)
		self.required_role = Role.ADMIN
		self.check_object_permissions(request, project)
		s = MembershipWriteSerializer(data=request.data)
		s.is_valid(raise_exception=True)
		try:
			user = User.objects.get(pk=s.validated_data["user_id"])
		except User.DoesNotExist:
			raise Http404("User not found")
		m = commands.add_member(project, user, s.validated_data["role"])
		return Response(
			{"user_id": m.user_id, "role": m.role},
			status=status.HTTP_201_CREATED,
		)

	@action(
		detail=True,
		methods=["delete"],
		url_path=r"members/(?P<user_id>[^/.]+)",
	)
	def remove_member(self, request, pk=None, user_id=None):
		self.required_role = Role.ADMIN
		project = self._get_object(pk)
		try:
			user = User.objects.get(pk=user_id)
		except User.DoesNotExist:
			raise Http404("User not found")
		commands.remove_member(project, user)
		return Response(status=status.HTTP_204_NO_CONTENT)
