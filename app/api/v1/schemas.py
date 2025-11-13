from pydantic import BaseModel, EmailStr
from pydantic import ConfigDict
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: Optional[datetime]

    # Pydantic v2 config
    model_config = ConfigDict(from_attributes=True)
