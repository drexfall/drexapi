from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1 import router as api_router
from app.db.session import client
from app.core.config import settings
import nltk


@asynccontextmanager
async def lifespan(app: FastAPI):
    nltk.download('stopwords')
    # Startup: verify connection and ensure indexes
    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"MongoDB ping failed: {e}")

    db = client[settings.MONGO_DB]
    db.users.create_index("email", unique=True)

    yield

    # Shutdown: close client
    try:
        client.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
