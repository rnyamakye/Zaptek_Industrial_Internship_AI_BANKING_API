"""Notification helper. Add to the session; the caller's commit saves it atomically with the
business change (so a rolled-back transaction never leaves a stray notification)."""
from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification


def notify(db: Session, user_id: int, type_: NotificationType, title: str, message: str) -> Notification:
    n = Notification(user_id=user_id, type=type_, title=title[:150], message=message)
    db.add(n)
    return n
