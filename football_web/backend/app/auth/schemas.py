from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional

from ..core.security import validate_password_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError(
                "Password must be at least 8 characters and include uppercase, "
                "lowercase, digit, and special character"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_role: str
    mfa_required: bool = False


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    mfa_enabled: bool

    model_config = {"from_attributes": True}


class MFASetupResponse(BaseModel):
    qr_code: str
    secret: str


class MFAVerifyRequest(BaseModel):
    code: str
    secret: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError(
                "Password must be at least 8 characters and include uppercase, "
                "lowercase, digit, and special character"
            )
        return v
