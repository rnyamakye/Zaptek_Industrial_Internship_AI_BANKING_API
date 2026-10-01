"""Admin/staff user management. Owner: Rick.

STAFF and ADMIN can list and view users. Only ADMIN can change a user's role or status.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, StaffUser, not_found
from app.core.audit import audit
from app.db.database import get_db
from app.models import User
from app.models.enums import UserRole, UserStatus
from app.schemas.admin import AdminUserUpdate
from app.schemas.auth import MeOut, UserOut

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserOut], summary="List users (STAFF/ADMIN)")
def list_users(
    response: Response,
    _: StaffUser,
    role: Optional[UserRole] = None,
    status_: Optional[UserStatus] = Query(default=None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if status_:
        query = query.where(User.status == status_)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    response.headers["X-Total-Count"] = str(total)
    return db.scalars(query.order_by(User.id).offset(skip).limit(limit)).all()


@router.get("/users/{user_id}", response_model=MeOut, summary="Get one user (STAFF/ADMIN)")
def get_user(user_id: int, _: StaffUser, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserOut, summary="Change role or status (ADMIN)")
def update_user(user_id: int, data: AdminUserUpdate, admin: AdminUser, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot change their own role or status")
    changes = {}
    if data.role is not None and data.role != user.role:
        changes["role"] = f"{user.role.value}->{data.role.value}"
        user.role = data.role
    if data.status is not None and data.status != user.status:
        changes["status"] = f"{user.status.value}->{data.status.value}"
        user.status = data.status
    if changes:
        db.commit()
        db.refresh(user)
        audit("admin_user_updated", admin_id=admin.id, target_user_id=user.id, **changes)
    return user
