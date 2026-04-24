from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.user import User, AuditLog, UserRole
from ..core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
    generate_qr_code_base64,
)
from .schemas import RegisterRequest, LoginRequest, ChangePasswordRequest

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15


async def _write_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    log = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(log)


async def register_user(
    db: AsyncSession,
    data: RegisterRequest,
    ip_address: Optional[str] = None,
) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.viewer,
    )
    db.add(user)
    await db.flush()
    await _write_audit(db, "register", user_id=user.id, ip_address=ip_address)
    return user


async def login_user(
    db: AsyncSession,
    data: LoginRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, str, bool]:
    """Returns (access_token, refresh_token, mfa_required)."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Check account lock
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked due to too many failed attempts",
        )

    if not verify_password(data.password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_DURATION_MINUTES)
        await _write_audit(
            db, "login_failed", user_id=user.id, ip_address=ip_address,
            details=f"Failed attempt #{user.failed_login_attempts}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # MFA check
    if user.mfa_enabled:
        if not data.totp_code:
            return "", "", True  # signal MFA required
        if not verify_totp(user.mfa_secret, data.totp_code):
            await _write_audit(
                db, "mfa_failed", user_id=user.id, ip_address=ip_address,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

    # Successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip_address

    access_token = create_access_token({"sub": user.email, "role": user.role.value})
    refresh_token = create_refresh_token({"sub": user.email})

    await _write_audit(
        db, "login_success", user_id=user.id,
        ip_address=ip_address, user_agent=user_agent,
    )
    return access_token, refresh_token, False


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:
    from jose import JWTError
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return create_access_token({"sub": user.email, "role": user.role.value})


async def setup_mfa(db: AsyncSession, user: User) -> Tuple[str, str]:
    """Returns (qr_code_base64, secret)."""
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, user.email)
    qr_code = generate_qr_code_base64(uri)
    # Persist the secret temporarily (not enabled until verified)
    user.mfa_secret = secret
    return qr_code, secret


async def verify_and_enable_mfa(db: AsyncSession, user: User, code: str, secret: str) -> None:
    if not verify_totp(secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")
    user.mfa_secret = secret
    user.mfa_enabled = True
    await _write_audit(db, "mfa_enabled", user_id=user.id)


async def disable_mfa(db: AsyncSession, user: User) -> None:
    user.mfa_secret = None
    user.mfa_enabled = False
    await _write_audit(db, "mfa_disabled", user_id=user.id)


async def change_password(
    db: AsyncSession,
    user: User,
    data: ChangePasswordRequest,
    ip_address: Optional[str] = None,
) -> None:
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.hashed_password = hash_password(data.new_password)
    await _write_audit(db, "password_changed", user_id=user.id, ip_address=ip_address)


async def logout_user(db: AsyncSession, user: User, ip_address: Optional[str] = None) -> None:
    await _write_audit(db, "logout", user_id=user.id, ip_address=ip_address)
