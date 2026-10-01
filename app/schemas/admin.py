from typing import Optional

from pydantic import BaseModel

from app.models.enums import UserRole, UserStatus


class AdminUserUpdate(BaseModel):
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
