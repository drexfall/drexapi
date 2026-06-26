"""Schema-driven validation for form submissions. De-DRF'd: raises
FormValidationError (payload is a str or per-field dict) instead of DRF's
serializers.ValidationError."""
from typing import Any

_ALLOWED_TYPES = {
	"text", "textarea", "email", "number", "url",
	"checkbox", "select", "multiselect", "date",
}


class FormValidationError(Exception):
	def __init__(self, detail):
		super().__init__(str(detail))
		self.detail = detail


def validate_schema(schema: Any) -> list[dict]:
	if not isinstance(schema, list):
		raise FormValidationError("schema must be a list")
	seen = set()
	for field in schema:
		if not isinstance(field, dict):
			raise FormValidationError("each field must be an object")
		name = field.get("name")
		ftype = field.get("type")
		if not name or not isinstance(name, str):
			raise FormValidationError("field.name required")
		if name in seen:
			raise FormValidationError(f"duplicate field name: {name}")
		seen.add(name)
		if ftype not in _ALLOWED_TYPES:
			raise FormValidationError(f"field.type must be one of {sorted(_ALLOWED_TYPES)}")
	return schema


def validate_submission(schema: list[dict], data: dict) -> dict:
	if not isinstance(data, dict):
		raise FormValidationError("data must be an object")
	out: dict[str, Any] = {}
	errors: dict[str, str] = {}
	for field in schema:
		name = field["name"]
		ftype = field["type"]
		required = bool(field.get("required"))
		val = data.get(name)
		if val in (None, "", []):
			if required:
				errors[name] = "required"
			continue
		try:
			out[name] = _coerce(ftype, val, field)
		except ValueError as exc:
			errors[name] = str(exc)
	if errors:
		raise FormValidationError(errors)
	return out


def _coerce(ftype: str, val: Any, field: dict) -> Any:
	if ftype in ("text", "textarea", "email", "url", "date"):
		if not isinstance(val, str):
			raise ValueError("must be string")
		return val
	if ftype == "number":
		try:
			return float(val)
		except (TypeError, ValueError):
			raise ValueError("must be number")
	if ftype == "checkbox":
		return bool(val)
	if ftype == "select":
		if val not in (field.get("options") or []):
			raise ValueError("invalid option")
		return val
	if ftype == "multiselect":
		options = set(field.get("options") or [])
		if not isinstance(val, list) or not all(v in options for v in val):
			raise ValueError("invalid options")
		return val
	return val
