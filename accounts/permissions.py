from rest_framework import permissions

from .models import ROLE_RANK, Membership, Role


class IsProjectMember(permissions.BasePermission):
	message = "Not a member of this project."

	def has_object_permission(self, request, view, obj):
		user = request.user
		if not user or not user.is_authenticated:
			return False
		if user.is_superuser:
			return True
		return Membership.objects.filter(user=user, project=obj).exists()


class HasProjectRole(permissions.BasePermission):
	"""Use via view attribute: required_role = Role.EDITOR."""

	message = "Insufficient role for this project."

	def has_object_permission(self, request, view, obj):
		user = request.user
		if not user or not user.is_authenticated:
			return False
		if user.is_superuser:
			return True
		required = getattr(view, "required_role", Role.VIEWER)
		if request.method in permissions.SAFE_METHODS:
			required = getattr(view, "read_role", Role.VIEWER)
		try:
			m = Membership.objects.get(user=user, project=obj)
		except Membership.DoesNotExist:
			return False
		return ROLE_RANK[m.role] >= ROLE_RANK[required]
