"""Auth0 bearer-token validation as a FastAPI dependency.

Ported from accounts/auth0.py + accounts/authentication.py, decoupled from
Django (reads es.config.Settings instead of django.conf.settings). JIT user
provisioning is intentionally dropped here — the FastAPI principal is the Auth0
`sub`; role/membership lookups move to a read model in slice 2.
"""
import threading
import time
from dataclasses import dataclass
from typing import Any

import jwt
import requests
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from es.config import Settings, get_settings


class Auth0Error(Exception):
	pass


@dataclass(frozen=True)
class Principal:
	sub: str
	email: str
	email_verified: bool
	raw: dict[str, Any]
	is_admin: bool = False
	username: str = ""


class _JWKSCache:
	def __init__(self, jwks_uri: str, ttl: int = 86_400):
		self._uri = jwks_uri
		self._ttl = ttl
		self._client: PyJWKClient | None = None
		self._loaded_at = 0.0
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
_jwks_lock = threading.Lock()


def _jwks_cache(settings: Settings) -> _JWKSCache:
	global _jwks
	if _jwks is None:
		with _jwks_lock:
			if _jwks is None:
				if not settings.auth0_domain:
					raise Auth0Error("AUTH0_DOMAIN not configured")
				_jwks = _JWKSCache(f"https://{settings.auth0_domain}/.well-known/jwks.json")
	return _jwks


def _claims_from_userinfo(token: str, settings: Settings) -> Principal:
	resp = requests.get(
		f"https://{settings.auth0_domain}/userinfo",
		headers={"Authorization": f"Bearer {token}"},
		timeout=5,
	)
	if resp.status_code != 200:
		raise Auth0Error(f"userinfo failed: {resp.status_code}")
	info = resp.json()
	sub = info.get("sub")
	if not sub:
		raise Auth0Error("userinfo missing sub")
	ns = settings.auth0_claims_namespace
	return Principal(
		sub=sub,
		email=info.get("email") or info.get(f"{ns}email", ""),
		email_verified=bool(info.get("email_verified") or info.get(f"{ns}email_verified")),
		raw=info,
	)


def verify_token(token: str, settings: Settings) -> Principal:
	if not token:
		raise Auth0Error("Empty token")

	# JWE access tokens (5 parts) are encrypted with Auth0 keys — validate via /userinfo
	if token.count(".") == 4:
		return _claims_from_userinfo(token, settings)

	try:
		signing_key = _jwks_cache(settings).client().get_signing_key_from_jwt(token).key
	except Auth0Error:
		raise
	except Exception as exc:
		raise Auth0Error(f"JWKS lookup failed: {exc}") from exc

	try:
		payload = jwt.decode(
			token,
			signing_key,
			algorithms=["RS256"],
			audience=settings.auth0_audience,
			issuer=f"https://{settings.auth0_domain}/",
			options={"require": ["exp", "iat", "sub"]},
		)
	except jwt.ExpiredSignatureError as exc:
		raise Auth0Error("Token expired") from exc
	except jwt.InvalidTokenError as exc:
		raise Auth0Error(f"Invalid token: {exc}") from exc

	sub = payload.get("sub")
	if not sub:
		raise Auth0Error("Token missing sub")
	ns = settings.auth0_claims_namespace
	return Principal(
		sub=sub,
		email=payload.get("email") or payload.get(f"{ns}email", ""),
		email_verified=bool(payload.get("email_verified") or payload.get(f"{ns}email_verified")),
		raw=payload,
	)


def require_principal(
	authorization: str | None = Header(default=None),
	settings: Settings = Depends(get_settings),
) -> Principal:
	if not authorization or not authorization.lower().startswith("bearer "):
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
	token = authorization.split(" ", 1)[1].strip()
	try:
		base = verify_token(token, settings)
	except Auth0Error as exc:
		raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))

	# JIT provision / refresh the UserProfile, then enrich the principal.
	from es.accounts.app import ProvisioningError, get_accounts_app

	try:
		doc = get_accounts_app().provision(
			sub=base.sub, email=base.email, email_verified=base.email_verified
		)
	except ProvisioningError as exc:
		raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
	return Principal(
		sub=base.sub,
		email=base.email,
		email_verified=base.email_verified,
		raw=base.raw,
		is_admin=bool(doc.get("is_admin")),
		username=doc.get("username", ""),
	)


def require_admin(principal: "Principal" = Depends(require_principal)) -> "Principal":
	if not principal.is_admin:
		raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin required")
	return principal
