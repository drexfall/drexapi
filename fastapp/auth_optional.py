"""Optional Auth0 principal — returns None instead of 401 when no/invalid token.

For endpoints that work anonymously but enrich behaviour when authenticated
(e.g. public form submit attributing the submitter)."""
from fastapi import Depends, Header

from es.config import Settings, get_settings
from fastapp.auth import Auth0Error, Principal, verify_token


def optional_principal(
	authorization: str | None = Header(default=None),
	settings: Settings = Depends(get_settings),
) -> Principal | None:
	if not authorization or not authorization.lower().startswith("bearer "):
		return None
	token = authorization.split(" ", 1)[1].strip()
	try:
		base = verify_token(token, settings)
	except Auth0Error:
		return None
	# best-effort provisioning; ignore failures for anonymous-friendly routes
	try:
		from es.accounts.app import get_accounts_app

		doc = get_accounts_app().provision(
			sub=base.sub, email=base.email, email_verified=base.email_verified
		)
		return Principal(
			sub=base.sub, email=base.email, email_verified=base.email_verified,
			raw=base.raw, is_admin=bool(doc.get("is_admin")), username=doc.get("username", ""),
		)
	except Exception:
		return base
