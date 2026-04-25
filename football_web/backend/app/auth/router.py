from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..core.dependencies import get_db, get_current_user
from ..core.config import settings
from ..models.user import User
from .schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    ChangePasswordRequest,
)
from . import service

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_COOKIE_OPTS = dict(
    httponly=True,
    samesite="strict",
    secure=settings.ENVIRONMENT == "production",
)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        "access_token",
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE_OPTS,
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth/refresh",
        **_COOKIE_OPTS,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    user = await service.register_user(db, data, ip_address=ip)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    access_token, refresh_token, mfa_required = await service.login_user(
        db, data, ip_address=ip, user_agent=ua
    )
    if mfa_required:
        return TokenResponse(access_token="", user_role="", mfa_required=True)

    _set_auth_cookies(response, access_token, refresh_token)

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    role = user.role.value if user else "viewer"
    return TokenResponse(access_token=access_token, user_role=role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = request.client.host if request.client else None
    await service.logout_user(db, current_user, ip_address=ip)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: Optional[str] = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    new_access = await service.refresh_access_token(db, refresh_token)
    response.set_cookie(
        "access_token",
        new_access,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_COOKIE_OPTS,
    )
    return TokenResponse(access_token=new_access, user_role="")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qr_code, secret = await service.setup_mfa(db, current_user)
    return MFASetupResponse(qr_code=qr_code, secret=secret)


@router.post("/mfa/verify", status_code=status.HTTP_200_OK)
async def mfa_verify(
    data: MFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.verify_and_enable_mfa(db, current_user, data.code, data.secret)
    return {"detail": "MFA enabled successfully"}


@router.delete("/mfa/disable", status_code=status.HTTP_200_OK)
async def mfa_disable(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.disable_mfa(db, current_user)
    return {"detail": "MFA disabled"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = request.client.host if request.client else None
    await service.change_password(db, current_user, data, ip_address=ip)
    return {"detail": "Password changed successfully"}
