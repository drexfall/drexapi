from typing import Dict
from bson import ObjectId


def serialize_user(doc: Dict) -> Dict:
    """Convert a MongoDB user document to a JSON-serializable dict."""
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")) if doc.get("_id") else None,
        "email": doc.get("email"),
        "is_active": doc.get("is_active", True),
        "created_at": doc.get("created_at"),
    }
