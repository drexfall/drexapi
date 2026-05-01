import threading
import time
from dataclasses import dataclass
from typing import Any

import jwt
import requests
from django.conf import settings
from jwt import PyJWKClient


class Auth0Error(Exception):
	pass


@dataclass(frozen=True)
class TokenClaims:
	sub: str
	email: str
	email_verified: bool
	raw: dict[str, Any]


class _JWKSCache:
	def __init__(self, jwks_uri: str, ttl: int = 86_400):
		self._uri = jwks_uri
		self._ttl = ttl
		self._client: PyJWKClient | None = None
		self._loaded_at: float = 0.0
		self._lock = threading.Lock()

	def client(self) -> PyJWKClient:
		now = time.time()
		if self._client is None or now - self._loaded_at > self._ttl:
			with self._lock:
				if self._client is None or time.time() - self._loaded_at > self._ttl:
					self._client = PyJWKClient(self._uri, cache_keys=True)
					self._loaded_at = time.time()
		return self._client


_jwks: _JWKSCache | None = None


def _get_jwks() -> _JWKSCache:
	global _jwks
	if _jwks is None:
		domain = settings.AUTH0_DOMAIN
		if not domain:
			raise Auth0Error("AUTH0_DOMAIN not configured")
		_jwks = _JWKSCache(f"https://{domain}/.well-known/jwks.json")
	return _jwks


def verify_token(token: str) -> TokenClaims:
	if not token:
		raise Auth0Error("Empty token")

	try:
		signing_key = _get_jwks().client().get_signing_key_from_jwt(token).key
	except Exception as exc:
		raise Auth0Error(f"JWKS lookup failed: {exc}") from exc

	try:
		payload = jwt.decode(
			token,
			signing_key,
			algorithms=["RS256"],
			audience=settings.AUTH0_AUDIENCE,
			issuer=f"https://{settings.AUTH0_DOMAIN}/",
			options={"require": ["exp", "iat", "sub"]},
		)
	except jwt.ExpiredSignatureError as exc:
		raise Auth0Error("Token expired") from exc
	except jwt.InvalidTokenError as exc:
		raise Auth0Error(f"Invalid token: {exc}") from exc

	sub = payload.get("sub")
	if not sub:
		raise Auth0Error("Token missing sub")

	return TokenClaims(
		sub=sub,
		email=payload.get("email") or payload.get(f"{settings.AUTH0_CLAIMS_NAMESPACE}email", ""),
		email_verified=bool(
			payload.get("email_verified")
			or payload.get(f"{settings.AUTH0_CLAIMS_NAMESPACE}email_verified")
		),
		raw=payload,
	)


def fetch_userinfo(access_token: str) -> dict[str, Any]:
	"""Fallback for tokens that lack email claim — hit Auth0 /userinfo."""
	resp = requests.get(
		f"https://{settings.AUTH0_DOMAIN}/userinfo",
		headers={"Authorization": f"Bearer {access_token}"},
		timeout=5,
	)
	if resp.status_code != 200:
		raise Auth0Error(f"userinfo failed: {resp.status_code}")
	return resp.json()
