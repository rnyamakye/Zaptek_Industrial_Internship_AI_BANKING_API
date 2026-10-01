"""Isolated in-memory test database. Every test gets fresh tables.

Shared fixtures (use them in your own tests):
  client                      FastAPI TestClient wired to the test DB
  db                          SQLAlchemy session on the test DB
  make_user(role=..., ...)    creates a user (+ customer profile for CUSTOMER) and returns the User
  auth_headers(user)          {"Authorization": "Bearer <access token>"} for that user
"""
import itertools
import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")  # must be set before the app is imported

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (make sure all models are registered on Base)
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CustomerProfile, User  # noqa: E402
from app.models.enums import UserRole, UserStatus  # noqa: E402

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_conn, _record):
    # SQLite ignores foreign keys unless enabled, so without this the tests would
    # accept data that PostgreSQL (production) rejects.
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


_counter = itertools.count(1)
TEST_PASSWORD = "Passw0rdTest"


@pytest.fixture()
def make_user(db):
    def _make(role=UserRole.CUSTOMER, status=UserStatus.ACTIVE, password=TEST_PASSWORD, email=None, phone=None):
        n = next(_counter)
        user = User(
            full_name=f"Test User {n}",
            email=email or f"user{n}@example.com",
            phone=phone or f"02400000{n:02d}",
            password_hash=hash_password(password),
            role=role,
            status=status,
        )
        if role == UserRole.CUSTOMER:
            user.profile = CustomerProfile(date_of_birth=date(1995, 5, 5), address="Accra")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def auth_headers():
    def _headers(user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}

    return _headers
