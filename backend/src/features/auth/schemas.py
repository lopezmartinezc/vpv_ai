from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from src.shared.permissions import Perm

# All Perm bits OR-ed together — the largest value a valid bitmap
# can take. Computed at import time so adding a new bit to Perm
# automatically updates the schema's upper bound (no more "Notas
# Marca = 1024 rejected because the schema is stuck at 1023").
_PERMISSIONS_MAX = sum(p.value for p in Perm)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    token: str
    username: str | None = None
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str | None
    is_admin: bool
    permissions: int


class InviteCreateRequest(BaseModel):
    target_user_id: int | None = None
    expires_days: int = Field(default=7, ge=1, le=30)


class InviteResponse(BaseModel):
    id: int
    token: str
    target_user_id: int | None
    target_display_name: str | None = None
    created_by_display_name: str
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime


class InviteStatusResponse(BaseModel):
    valid: bool
    target_user_id: int | None = None
    target_display_name: str | None = None
    expired: bool = False


class UserWithoutPasswordResponse(BaseModel):
    id: int
    username: str
    display_name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class SetPermissionsRequest(BaseModel):
    permissions: int = Field(ge=0, le=_PERMISSIONS_MAX)


class AdminUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str | None
    is_admin: bool
    permissions: int
    has_password: bool
    has_session: bool
    telegram_chat_id: str | None


class AdminCreateUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    is_admin: bool = False


class AdminUpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telegram_chat_id: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8)
