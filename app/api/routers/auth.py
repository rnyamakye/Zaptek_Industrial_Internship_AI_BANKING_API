"""Auth router. Owner: Rick."""
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.audit import audit
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import (
    REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.models import CustomerProfile, User
from app.models.enums import UserRole, UserStatus
from app.schemas.auth import MeOut, RefreshRequest, RegisterRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()

INVALID_LOGIN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/register",
    response_model=MeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer",
    responses={409: {"description": "Email or phone already registered"}, 422: {"description": "Validation error"}},
)
@limiter.limit(settings.register_rate_limit)
def register(request: Request, data: RegisterRequest, db: Session = Depends(get_db)):
    """Creates a CUSTOMER user and their customer profile. The role is always CUSTOMER;
    STAFF and ADMIN accounts are created by an admin (see /admin/users)."""
    if db.scalar(select(User).where(func.lower(User.email) == data.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if db.scalar(select(User).where(User.phone == data.phone)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")

    user = User(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=UserRole.CUSTOMER,
        status=UserStatus.ACTIVE,
    )
    user.profile = CustomerProfile(
        date_of_birth=data.date_of_birth, address=data.address, occupation=data.occupation
    )
    db.add(user)
    try:
        db.commit()  # user + profile are saved together or not at all
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or phone already registered")
    db.refresh(user)
    audit("register", user_id=user.id)
    return user


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in (form fields: username = email, password)",
    responses={401: {"description": "Invalid email or password"}, 403: {"description": "Account suspended"}},
)
@limiter.limit(settings.login_rate_limit)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    ok = verify_password(form.password, user.password_hash if user else None)
    if not user or not ok:
        audit("login_failed", email=email, ip=request.client.host if request.client else "unknown")
        raise INVALID_LOGIN
    if user.status != UserStatus.ACTIVE:
        audit("login_blocked", user_id=user.id, status=user.status.value)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    audit("login_success", user_id=user.id)
    return _token_pair(user)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a new access + refresh token",
    responses={401: {"description": "Invalid or expired refresh token"}},
)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token, REFRESH)
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    audit("token_refreshed", user_id=user.id)
    return _token_pair(user)


@router.get("/me", response_model=MeOut, summary="Current user and profile")
def me(user: CurrentUser):
    return user
