from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.rate_limit import limiter
from src.features.auth.schemas import (
    AdminUserResponse,
    InviteCreateRequest,
    InviteResponse,
    InviteStatusResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserWithoutPasswordResponse,
)
from src.features.auth.service import AuthService
from src.shared.dependencies import get_current_admin, get_current_user, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    return await service.login(body.username, body.password)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> UserResponse:
    return await service.get_me(int(user["sub"]))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    user: dict = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    return await service.refresh(int(user["sub"]))


@router.get("/invite/{token}", response_model=InviteStatusResponse)
@limiter.limit("10/minute")
async def validate_invite(
    request: Request,
    token: str,
    service: AuthService = Depends(_get_service),
) -> InviteStatusResponse:
    return await service.validate_invite(token)


@router.post("/register", response_model=TokenResponse)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    service: AuthService = Depends(_get_service),
) -> TokenResponse:
    return await service.register_with_invite(body.token, body.password, body.username)


@router.post("/admin/invite", response_model=InviteResponse)
async def create_invite(
    body: InviteCreateRequest,
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> InviteResponse:
    return await service.create_invite(int(admin["sub"]), body.target_user_id, body.expires_days)


@router.get("/admin/invites", response_model=list[InviteResponse])
async def list_invites(
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> list[InviteResponse]:
    return await service.list_invites()


@router.get("/admin/users-without-password", response_model=list[UserWithoutPasswordResponse])
async def users_without_password(
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> list[UserWithoutPasswordResponse]:
    return await service.get_users_without_password()


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def list_users(
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> list[AdminUserResponse]:
    return await service.list_users()


@router.put("/admin/users/{user_id}/toggle-admin", response_model=AdminUserResponse)
async def toggle_admin(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> AdminUserResponse:
    return await service.toggle_admin(user_id, int(admin["sub"]))


@router.post("/admin/users/{user_id}/reset-password", response_model=InviteResponse)
async def reset_password(
    user_id: int,
    admin: dict = Depends(get_current_admin),
    service: AuthService = Depends(_get_service),
) -> InviteResponse:
    return await service.reset_password(user_id, int(admin["sub"]))
