"""Write model — UserProfile aggregate (replaces Django User + accounts.Profile).

Identity is the Auth0 `sub`. Provisioning is JIT on first authenticated request.
sub->id and username uniqueness are served by the profile read model.
"""
import re

from eventsourcing.domain import Aggregate, event

_SLUG = re.compile(r"[^a-z0-9]+")


def slug_from_email(email: str) -> str:
	base = _SLUG.sub("-", email.split("@")[0].lower()).strip("-")
	return (base or "user")[:64]


class UserProfile(Aggregate):
	@event("Provisioned")
	def __init__(self, sub: str, email: str, username: str, email_verified: bool):
		self.sub = sub
		self.email = email
		self.username = username
		self.display_name = ""
		self.bio = ""
		self.avatar_url = ""
		self.links: dict = {}
		self.is_public = False
		self.is_admin = False
		self.email_verified = email_verified
		self.deleted = False

	@event("EmailUpdated")
	def update_email(self, email: str, email_verified: bool) -> None:
		self.email = email
		self.email_verified = email_verified

	@event("ProfileUpdated")
	def update_profile(self, changes: dict) -> None:
		for key in ("display_name", "bio", "avatar_url", "links", "is_public"):
			if changes.get(key) is not None:
				setattr(self, key, changes[key])

	@event("AdminSet")
	def set_admin(self, is_admin: bool) -> None:
		self.is_admin = is_admin

	@event("Deleted")
	def delete(self) -> None:
		self.deleted = True
