import logging

from django.conf import settings
from mongoengine import get_connection
from pymongo import ASCENDING, MongoClient
from pymongo.server_api import ServerApi

logger = logging.getLogger(__name__)

_ALIAS = "default"
_connected = False


class MongoConnector:
    def __init__(self):
        self.client = None
        self.connect_if_needed()

    def connect_if_needed(self) -> None:

        uri = getattr(settings, "MONGO_URI", None)
        db = getattr(settings, "MONGO_DB", None)
        if not uri or not db:
            logger.warning("Mongo not configured; skipping connect")
            return
        # Create a new client and connect to the server
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        # Send a ping to confirm a successful connection
        try:
            self.client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(e)

    def get_db(self, alias=_ALIAS):
        self.connect_if_needed()
        return get_connection(_ALIAS)[settings.MONGO_DB]

    def ensure_project_collection(self, project_id) -> None:
        """Create a collection and indexes for a new project."""
        db = self.get_db()
        name = f"project_{project_id.hex if hasattr(project_id, 'hex') else str(project_id).replace('-', '')}"
        if name not in db.list_collection_names():
            db.create_collection(name)
        coll = db[name]
        coll.create_index([("doc_type", ASCENDING)])
        coll.create_index([("created_at", ASCENDING)])

    def drop_project_collection(self, project_id) -> None:
        db = self.get_db()
        name = f"project_{project_id.hex if hasattr(project_id, 'hex') else str(project_id).replace('-', '')}"
        if name in db.list_collection_names():
            db.drop_collection(name)

    def project_collection(self, project_id):
        db = self.get_db()
        name = f"project_{project_id.hex if hasattr(project_id, 'hex') else str(project_id).replace('-', '')}"
        return db[name]
