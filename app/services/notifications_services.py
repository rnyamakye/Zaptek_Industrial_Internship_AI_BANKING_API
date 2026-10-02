from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.enums import NotificationType


def create_notification(
    db: Session,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        read=False,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification