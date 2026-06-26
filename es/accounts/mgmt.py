"""Auth0 Management API (password reset, user delete). De-Djangoed from
accounts/mgmt_api.py — reads es.config.Settings instead of django settings."""
import threading
import time

import requests

from es.config import get_settings


class Auth0MgmtError(Exception):
	pass


class _TokenCache:
	def __init__(self) -> None:
		self._token: str | None = None
		self._expires_at = 0.0
		self._lock = threading.Lock()

	def get(self) -> str:
		s = get_settings()
		now = time.time()
		if self._token and now < self._expires_at - 60:
			return self._token
		with self._lock:
			if self._token and time.time() < self._expires_at - 60:
				return self._token
			resp = requests.post(
				f"https://{s.auth0_domain}/oauth/token",
				json={
					"client_id": s.auth0_mgmt_client_id,
					"client_secret": s.auth0_mgmt_client_secret,
					"audience": f"https://{s.auth0_domain}/api/v2/",
					"grant_type": "client_credentials",
				},
				timeout=10,
			)
			if resp.status_code != 200:
				raise Auth0MgmtError(f"M2M token fetch failed: {resp.status_code} {resp.text}")
			data = resp.json()
			self._token = data["access_token"]
			self._expires_at = time.time() + int(data.get("expires_in", 3600))
			return self._token


_cache = _TokenCache()


def _headers() -> dict[str, str]:
	return {"Authorization": f"Bearer {_cache.get()}", "Content-Type": "application/json"}


def delete_user(sub: str) -> None:
	s = get_settings()
	resp = requests.delete(
		f"https://{s.auth0_domain}/api/v2/users/{sub}", headers=_headers(), timeout=10
	)
	if resp.status_code not in (204, 200):
		raise Auth0MgmtError(f"delete_user failed: {resp.status_code} {resp.text}")


def trigger_password_reset(email: str, connection: str = "Username-Password-Authentication") -> None:
	s = get_settings()
	resp = requests.post(
		f"https://{s.auth0_domain}/dbconnections/change_password",
		json={"client_id": s.auth0_client_id, "email": email, "connection": connection},
		timeout=10,
	)
	if resp.status_code not in (200, 201):
		raise Auth0MgmtError(f"password reset failed: {resp.status_code} {resp.text}")
