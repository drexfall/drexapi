from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from bson import ObjectId
from bson.errors import InvalidId

from app.api.v1 import schemas
from app.db import models
from app.db.session import get_db
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/users", tags=["users"])


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


@router.post("/", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Database = Depends(get_db)):
    existing = db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = get_password_hash(user.password)
    doc = {
        "email": user.email,
        "hashed_password": hashed,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    result = db.users.insert_one(doc)
    created = db.users.find_one({"_id": result.inserted_id})
    return models.serialize_user(created)


@router.get("/", response_model=List[schemas.UserOut])
def list_users(skip: int = 0, limit: int = 100, db: Database = Depends(get_db)):
    cursor = db.users.find().skip(int(skip)).limit(int(limit))
    return [models.serialize_user(doc) for doc in cursor]


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: str, db: Database = Depends(get_db)):
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = db.users.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return models.serialize_user(user)
