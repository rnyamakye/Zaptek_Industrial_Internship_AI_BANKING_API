"""Create the first ADMIN account (there is no public way to create one).

Usage:  python -m app.db.create_admin admin@example.com 'StrongPass123' 'Admin Name' 0240000000
Run it against the production database by setting DATABASE_URL first (Render shell).
"""
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import User
from app.models.enums import UserRole, UserStatus


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Administrator"
    phone = sys.argv[4] if len(sys.argv) > 4 else "0000000000"
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.email) == email)):
            print(f"User {email} already exists")
            return 1
        db.add(User(full_name=name, email=email, phone=phone, password_hash=hash_password(password),
                    role=UserRole.ADMIN, status=UserStatus.ACTIVE))
        db.commit()
    print(f"Admin {email} created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
