import uuid
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, field_validator

from app.models.user import UserRole
from app.schemas.common import BaseSchema


class UserCreate(BaseSchema):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.viewer

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseSchema):
    email: EmailStr
    password: str


class UserRead(BaseSchema):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseSchema):
    sub: str  # user id
    role: str
    exp: int
    type: str  # "access" or "refresh"


class TokenRefresh(BaseSchema):
    refresh_token: str
