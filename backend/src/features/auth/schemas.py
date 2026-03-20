from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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
    permissions: int = Field(ge=0, le=1023)


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
