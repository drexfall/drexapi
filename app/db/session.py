from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from app.core.config import settings

# Create a global Mongo client (will be reused by FastAPI dependency)
client = MongoClient(settings.MONGODB_URI, server_api=ServerApi('1'))


def get_db():
    """Dependency that yields a pymongo Database object."""
    db = client[settings.MONGO_DB]
    try:
        yield db
    finally:
        # do not close the global client here; let the process close it on shutdown
        pass
