"""drexapi — event-sourced FastAPI application (replaces the Django project).

ASGI entrypoint: `uvicorn fastapp.main:app`.
"""
import warnings

# FastAPI re-wraps aliased request-body fields in a TypeAdapter, which spuriously
# warns that `validation_alias` "has no effect" — it does (see forms `schema` field).
warnings.filterwarnings("ignore", message=r".*validation_alias.*has no effect.*")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from fastapp.routers import accounts, admin, carousels, forms, misc, projects, scan

app = FastAPI(title="drexapi", version="1.0.0")

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# core / api
app.include_router(projects.router)
app.include_router(forms.router)
app.include_router(scan.crud)
app.include_router(carousels.router)
app.include_router(misc.router)
# accounts / profiles
app.include_router(accounts.auth_router)
app.include_router(accounts.account_router)
app.include_router(accounts.profiles_router)
# admin
app.include_router(admin.router)
# public scan resolver (kept last; /scan/{code_id})
app.include_router(scan.public)


@app.get("/health", tags=["meta"])
def health() -> dict:
	return {"status": "ok"}
