"""Notifications router (own notifications only)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, not_found
from app.db.database import get_db
from app.models import Notification
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse], summary="My notifications (newest first)")
def list_notifications(
    user: CurrentUser,
    response: Response,
    unread: Optional[bool] = Query(default=None, description="true = only unread"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread:
        query = query.where(Notification.read.is_(False))
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count()).select_from(query.subquery())))
    return db.scalars(query.order_by(Notification.id.desc()).offset(skip).limit(limit)).all()


@router.patch("/{notification_id}/read", response_model=NotificationResponse, summary="Mark as read")
def mark_read(notification_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise not_found()
    n.read = True
    db.commit()
    db.refresh(n)
    return n
