from django.contrib.auth import get_user_model
from django.db import transaction

from .auth0 import TokenClaims, fetch_userinfo
from .models import AuditLog, Profile

User = get_user_model()


class ProvisioningError(Exception):
	pass


def _username_from_sub(sub: str) -> str:
	return sub.replace("|", "_")[:150]


@transaction.atomic
def jit_provision_user(claims: TokenClaims, access_token: str | None = None):
	email = claims.email
	email_verified = claims.email_verified

	if not email and access_token:
		info = fetch_userinfo(access_token)
		email = info.get("email", "")
		email_verified = bool(info.get("email_verified"))

	if not email:
		raise ProvisioningError("Token has no email claim")
	if not email_verified:
		raise ProvisioningError("Email not verified")

	try:
		profile = Profile.objects.select_related("user").get(external_id=claims.sub)
		user = profile.user
		changed = False
		if user.email != email:
			user.email = email
			changed = True
		if changed:
			user.save(update_fields=["email"])
		if not profile.email_verified:
			profile.email_verified = True
			profile.save(update_fields=["email_verified", "updated_at"])
		return user
	except Profile.DoesNotExist:
		pass

	username = _username_from_sub(claims.sub)
	user, created = User.objects.get_or_create(
		username=username,
		defaults={"email": email},
	)
	if not created and user.email != email:
		user.email = email
		user.save(update_fields=["email"])
	user.set_unusable_password()
	user.save(update_fields=["password"])

	Profile.objects.create(
		user=user,
		external_id=claims.sub,
		email_verified=email_verified,
	)
	AuditLog.objects.create(
		actor=user,
		action="user.provisioned",
		target_type="user",
		target_id=str(user.pk),
		metadata={"sub": claims.sub},
	)
	return user
