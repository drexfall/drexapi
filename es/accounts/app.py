"""Accounts application + projection + system + JIT provisioning.

Combines command side, read-model projection and runner wiring for the
UserProfile aggregate (kept in one module to limit churn across the migration).
"""
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.dispatch import singledispatchmethod
from eventsourcing.system import ProcessApplication, SingleThreadedRunner, System

from es.config import get_settings

from . import readmodel
from .domain import UserProfile, slug_from_email


class ProvisioningError(Exception):
	pass


def _now() -> str:
	return datetime.now(timezone.utc).isoformat()


class Accounts(Application):
	def _unique_username(self, base: str) -> str:
		store = readmodel.get_profile_store()
		candidate = base[:64]
		i = 1
		while store.username_exists(candidate):
			i += 1
			suffix = f"-{i}"
			candidate = f"{base[:64 - len(suffix)]}{suffix}"
		return candidate

	def provision(self, *, sub: str, email: str, email_verified: bool) -> dict:
		if not email:
			raise ProvisioningError("Token has no email claim")
		if not email_verified:
			raise ProvisioningError("Email not verified")

		store = readmodel.get_profile_store()
		existing = store.get_by_sub(sub)
		if existing:
			if existing["email"] != email or existing["email_verified"] != email_verified:
				profile = self.repository.get(UUID(existing["id"]))
				profile.update_email(email, email_verified)
				self.save(profile)
			return store.get_by_sub(sub)

		profile = UserProfile(
			sub=sub,
			email=email,
			username=self._unique_username(slug_from_email(email)),
			email_verified=email_verified,
		)
		self.save(profile)
		readmodel.get_audit_store().append(
			{
				"action": "user.provisioned",
				"actor": sub,
				"target_type": "user",
				"target_id": sub,
				"metadata": {"sub": sub},
				"created_at": _now(),
			}
		)
		return store.get_by_sub(sub)

	def get_by_sub(self, sub: str) -> dict | None:
		return readmodel.get_profile_store().get_by_sub(sub)

	def update_profile(self, sub: str, changes: dict) -> dict:
		doc = self._require(sub)
		profile = self.repository.get(UUID(doc["id"]))
		profile.update_profile(changes)
		self.save(profile)
		return readmodel.get_profile_store().get_by_sub(sub)

	def set_admin(self, sub: str, is_admin: bool) -> dict:
		doc = self._require(sub)
		profile = self.repository.get(UUID(doc["id"]))
		profile.set_admin(is_admin)
		self.save(profile)
		return readmodel.get_profile_store().get_by_sub(sub)

	def delete(self, sub: str) -> None:
		doc = readmodel.get_profile_store().get_by_sub(sub)
		if not doc:
			return
		profile = self.repository.get(UUID(doc["id"]))
		profile.delete()
		self.save(profile)

	def _require(self, sub: str) -> dict:
		doc = readmodel.get_profile_store().get_by_sub(sub)
		if not doc:
			raise ProvisioningError(f"no profile for {sub}")
		return doc


class ProfileReadModel(ProcessApplication):
	@singledispatchmethod
	def policy(self, domain_event, processing_event):
		"""ignore"""

	@policy.register
	def _provisioned(self, domain_event: UserProfile.Provisioned, processing_event):
		ts = domain_event.timestamp.isoformat()
		readmodel.get_profile_store().upsert(
			{
				"id": str(domain_event.originator_id),
				"sub": domain_event.sub,
				"username": domain_event.username,
				"email": domain_event.email,
				"display_name": "",
				"bio": "",
				"avatar_url": "",
				"links": {},
				"is_public": False,
				"is_admin": False,
				"email_verified": domain_event.email_verified,
				"created_at": ts,
				"updated_at": ts,
			}
		)

	@policy.register
	def _email(self, domain_event: UserProfile.EmailUpdated, processing_event):
		readmodel.get_profile_store().patch(
			str(domain_event.originator_id),
			{"email": domain_event.email, "email_verified": domain_event.email_verified, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _profile(self, domain_event: UserProfile.ProfileUpdated, processing_event):
		fields = {
			k: v
			for k, v in domain_event.changes.items()
			if v is not None and k in ("display_name", "bio", "avatar_url", "links", "is_public")
		}
		fields["updated_at"] = domain_event.timestamp.isoformat()
		readmodel.get_profile_store().patch(str(domain_event.originator_id), fields)

	@policy.register
	def _admin(self, domain_event: UserProfile.AdminSet, processing_event):
		readmodel.get_profile_store().patch(
			str(domain_event.originator_id),
			{"is_admin": domain_event.is_admin, "updated_at": domain_event.timestamp.isoformat()},
		)

	@policy.register
	def _deleted(self, domain_event: UserProfile.Deleted, processing_event):
		readmodel.get_profile_store().delete(str(domain_event.originator_id))


@lru_cache
def get_runner() -> SingleThreadedRunner:
	system = System(pipes=[[Accounts, ProfileReadModel]])
	runner = SingleThreadedRunner(system, env=get_settings().es_env())
	runner.start()
	return runner


def get_accounts_app() -> Accounts:
	return get_runner().get(Accounts)
