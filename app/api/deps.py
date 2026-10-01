"""Shared auth dependencies. Owner: Rick. Everyone else imports from here; nobody re-implements auth.

Usage in a router:

    from app.api.deps import CurrentUser, CurrentProfile, ensure_customer_access, require_staff

    @router.get("/accounts/{id}")
    def get_account(id: int, user: CurrentUser, db: Session = Depends(get_db)):
        account = db.get(Account, id)
        if account is None:
            raise not_found()
        ensure_customer_access(user, account.customer_id)   # 404 if it belongs to someone else
        ...

Rules: CUSTOMER sees only their own data. STAFF and ADMIN can see everyone's data.
Other customers' resources return 404 (not 403) so their existence is not revealed.
"""
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import ACCESS, decode_token
from app.db.database import get_db
from app.models import CustomerProfile, User
from app.models.enums import UserRole, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def not_found(detail: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_token(token, ACCESS)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise _credentials_error
    user = db.get(User, user_id)
    if user is None:
        raise _credentials_error
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Dependency factory: `Depends(require_roles(UserRole.ADMIN))`."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


require_staff = require_roles(UserRole.STAFF, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
StaffUser = Annotated[User, Depends(require_staff)]
AdminUser = Annotated[User, Depends(require_admin)]


def is_staff(user: User) -> bool:
    return user.role in (UserRole.STAFF, UserRole.ADMIN)


def get_current_profile(user: CurrentUser) -> CustomerProfile:
    """The customer profile of the logged-in user. STAFF/ADMIN have none, so this is customer-only."""
    if user.profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No customer profile for this user")
    return user.profile


CurrentProfile = Annotated[CustomerProfile, Depends(get_current_profile)]


def can_access_customer(user: User, customer_id: int) -> bool:
    """customer_id is a customer_profiles.id (accounts, loans, beneficiaries... point to it)."""
    if is_staff(user):
        return True
    return user.profile is not None and user.profile.id == customer_id


def ensure_customer_access(user: User, customer_id: int) -> None:
    if not can_access_customer(user, customer_id):
        raise not_found()
