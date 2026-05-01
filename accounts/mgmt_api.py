import time
import threading

import requests
from django.conf import settings


class Auth0MgmtError(Exception):
	pass


class _TokenCache:
	def __init__(self):
		self._token: str | None = None
		self._expires_at: float = 0.0
		self._lock = threading.Lock()

	def get(self) -> str:
		now = time.time()
		if self._token and now < self._expires_at - 60:
			return self._token
		with self._lock:
			if self._token and time.time() < self._expires_at - 60:
				return self._token
			resp = requests.post(
				f"https://{settings.AUTH0_DOMAIN}/oauth/token",
				json={
					"client_id": settings.AUTH0_MGMT_CLIENT_ID,
					"client_secret": settings.AUTH0_MGMT_CLIENT_SECRET,
					"audience": f"https://{settings.AUTH0_DOMAIN}/api/v2/",
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
	return {
		"Authorization": f"Bearer {_cache.get()}",
		"Content-Type": "application/json",
	}


def delete_user(sub: str) -> None:
	resp = requests.delete(
		f"https://{settings.AUTH0_DOMAIN}/api/v2/users/{sub}",
		headers=_headers(),
		timeout=10,
	)
	if resp.status_code not in (204, 200):
		raise Auth0MgmtError(f"delete_user failed: {resp.status_code} {resp.text}")


def trigger_password_reset(email: str, connection: str = "Username-Password-Authentication") -> None:
	resp = requests.post(
		f"https://{settings.AUTH0_DOMAIN}/dbconnections/change_password",
		json={
			"client_id": settings.AUTH0_CLIENT_ID,
			"email": email,
			"connection": connection,
		},
		timeout=10,
	)
	if resp.status_code not in (200, 201):
		raise Auth0MgmtError(f"password reset failed: {resp.status_code} {resp.text}")
