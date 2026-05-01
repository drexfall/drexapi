from rest_framework import authentication, exceptions

from .auth0 import Auth0Error, verify_token
from .services import ProvisioningError, jit_provision_user


class Auth0Authentication(authentication.BaseAuthentication):
	keyword = "Bearer"

	def authenticate(self, request):
		header = authentication.get_authorization_header(request).decode("utf-8")
		if not header or not header.lower().startswith(self.keyword.lower() + " "):
			return None

		token = header.split(" ", 1)[1].strip()
		try:
			claims = verify_token(token)
		except Auth0Error as exc:
			raise exceptions.AuthenticationFailed(str(exc))

		try:
			user = jit_provision_user(claims, access_token=token)
		except ProvisioningError as exc:
			raise exceptions.AuthenticationFailed(str(exc))

		return user, claims

	def authenticate_header(self, request):
		return self.keyword
