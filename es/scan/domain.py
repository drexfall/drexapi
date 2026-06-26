"""Write model — ScanCode aggregate (short-code -> URL redirect, hit-counted)."""
import secrets

from eventsourcing.domain import Aggregate, event


def gen_code() -> str:
	return secrets.token_urlsafe(6)


class ScanCode(Aggregate):
	@event("Created")
	def __init__(self, owner_id: str, code_id: str, label: str, target_url: str):
		self.owner_id = owner_id
		self.code_id = code_id
		self.label = label
		self.target_url = target_url
		self.is_active = True
		self.hit_count = 0
		self.last_hit_at = None

	@event("Updated")
	def update(self, changes: dict) -> None:
		for key in ("label", "target_url", "is_active"):
			if changes.get(key) is not None:
				setattr(self, key, changes[key])

	@event("Hit")
	def hit(self, at: str) -> None:
		self.hit_count += 1
		self.last_hit_at = at
