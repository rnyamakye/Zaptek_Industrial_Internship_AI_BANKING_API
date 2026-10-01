"""Auth request/response schemas. Sensitive fields (password_hash) are never exposed."""
import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.enums import UserRole, UserStatus, VerificationStatus

PHONE_RE = re.compile(r"^\+?\d{9,15}$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(description="Digits with optional leading +, e.g. 0241234567 or +233241234567")
    password: str = Field(min_length=8, description="At least 8 characters with a letter and a digit")
    date_of_birth: date
    address: str = Field(min_length=3, max_length=255)
    occupation: Optional[str] = Field(default=None, max_length=100)

    @field_validator("full_name", "address")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = v.replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("Invalid phone number")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must contain at least one letter and one digit")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _adult(cls, v: date) -> date:
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Customer must be at least 18 years old")
        if age > 120:
            raise ValueError("Invalid date of birth")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_of_birth: date
    address: str
    occupation: Optional[str]
    verification_status: VerificationStatus


class MeOut(UserOut):
    """Current user plus their customer profile (null for STAFF/ADMIN)."""

    profile: Optional[ProfileOut] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str
