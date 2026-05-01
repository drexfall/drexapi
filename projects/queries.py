from django.http import Http404

from accounts.models import Membership

from .models import Project
from .mongo import MongoConnector


def get_project_or_404(project_id) -> Project:
    try:
        return Project.objects.get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise Http404("Project not found") from exc


def list_projects_for_user(user):
    return Project.objects.filter(memberships__user=user).distinct()


def read_project_view(project: Project) -> dict:
    """Prefer Mongo read-model; fall back to pgsql if projection missing."""
    try:
        coll = MongoConnector().project_collection(project.id)
        doc = coll.find_one({"doc_type": "read_model"})
    except Exception:
        doc = None
    if doc:
        doc.pop("_id", None)
        return doc
    return {
        "doc_type": "read_model",
        "id": str(project.id),
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "owner_id": project.owner_id,
        "metadata": project.metadata,
        "status": project.status,
        "source": "pgsql_fallback",
    }


def list_documents(project: Project, limit: int = 100, skip: int = 0) -> list[dict]:
    coll = project_collection(project.id)
    cursor = coll.find({"doc_type": "document"}).skip(skip).limit(limit)
    out = []
    for d in cursor:
        d["_id"] = str(d["_id"])
        out.append(d)
    return out


def get_user_role(user, project: Project) -> str | None:
    try:
        return Membership.objects.get(user=user, project=project).role
    except Membership.DoesNotExist:
        return None
