from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.mgmt_api import Auth0MgmtError, delete_user, trigger_password_reset
from accounts.models import AuditLog, Profile


class ProfileSerializer(serializers.Serializer):
	id = serializers.IntegerField()
	username = serializers.CharField()
	email = serializers.EmailField()
	external_id = serializers.CharField()
	email_verified = serializers.BooleanField()


def _profile_payload(user) -> dict:
	profile: Profile = getattr(user, "profile", None)
	return {
		"id": user.pk,
		"username": user.username,
		"email": user.email,
		"external_id": profile.external_id if profile else "",
		"email_verified": profile.email_verified if profile else False,
	}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
	return Response(_profile_payload(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync(request):
	"""JIT provisioning already happens in auth class; this just echoes profile."""
	return Response(_profile_payload(request.user))


class _ResetThrottle(ScopedRateThrottle):
	scope = "password_reset"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_ResetThrottle])
def password_reset(request):
	email = request.user.email
	if not email:
		return Response({"detail": "No email on account."}, status=status.HTTP_400_BAD_REQUEST)
	try:
		trigger_password_reset(email)
	except Auth0MgmtError as exc:
		return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
	AuditLog.objects.create(
		actor=request.user, action="password.reset_requested",
		target_type="user", target_id=str(request.user.pk),
	)
	return Response({"status": "sent"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_me(request):
	user = request.user
	profile: Profile | None = getattr(user, "profile", None)
	sub = profile.external_id if profile else None
	if sub:
		try:
			delete_user(sub)
		except Auth0MgmtError as exc:
			return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
	AuditLog.objects.create(
		actor=None, action="user.deleted",
		target_type="user", target_id=str(user.pk),
		metadata={"sub": sub or ""},
	)
	user.delete()
	return Response(status=status.HTTP_204_NO_CONTENT)
