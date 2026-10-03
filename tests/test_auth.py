import logging
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.core.security import (
    ACCESS,
    REFRESH,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.models.enums import UserStatus
from tests.conftest import TEST_PASSWORD

REGISTER = {
    "full_name": "Ama Mensah",
    "email": "Ama@Example.com",
    "phone": "0241234567",
    "password": "Secret123",
    "date_of_birth": "1998-03-14",
    "address": "12 Ring Road, Accra",
    "occupation": "Teacher",
}


def login(client, email, password=TEST_PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


# ---------- registration ----------

def test_register_creates_customer_and_profile_without_leaking_hash(client, db):
    r = client.post("/auth/register", json=REGISTER)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "ama@example.com"  # normalised to lowercase
    assert body["role"] == "CUSTOMER" and body["status"] == "ACTIVE"
    assert body["profile"]["verification_status"] == "PENDING"
    assert "password" not in body and "password_hash" not in body
    user = db.query(User).one()
    assert user.password_hash != REGISTER["password"]
    assert verify_password(REGISTER["password"], user.password_hash)


def test_register_cannot_choose_own_role(client):
    r = client.post("/auth/register", json={**REGISTER, "role": "ADMIN"})
    assert r.status_code == 201
    assert r.json()["role"] == "CUSTOMER"


def test_register_duplicate_email_is_case_insensitive(client):
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    r = client.post("/auth/register", json={**REGISTER, "email": "AMA@example.COM", "phone": "0249999999"})
    assert r.status_code == 409


def test_register_duplicate_phone(client):
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    r = client.post("/auth/register", json={**REGISTER, "email": "other@example.com"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"email": "not-an-email"},
        {"phone": "abc"},
        {"password": "short1"},
        {"password": "allletters"},
        {"password": "12345678"},
        {"password": "a1" * 40},  # over 72 bytes
        {"date_of_birth": "2015-01-01"},  # under 18
        {"full_name": "A"},
    ],
)
def test_register_rejects_invalid_input(client, change):
    assert client.post("/auth/register", json={**REGISTER, **change}).status_code == 422


def test_register_missing_fields(client):
    assert client.post("/auth/register", json={"email": "a@b.com"}).status_code == 422


# ---------- login ----------

def test_login_returns_working_token_pair(client, make_user):
    user = make_user()
    r = login(client, user.email)
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] > 0
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == user.id


def test_login_email_is_case_insensitive(client, make_user):
    user = make_user(email="mixed@example.com")
    assert login(client, "MIXED@Example.com").status_code == 200


def test_login_wrong_password_and_unknown_email_look_identical(client, make_user):
    user = make_user()
    wrong_pw = login(client, user.email, "WrongPass1")
    unknown = login(client, "nobody@example.com")
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_login_suspended_user_blocked(client, make_user):
    user = make_user(status=UserStatus.SUSPENDED)
    assert login(client, user.email).status_code == 403


def test_login_failure_is_audited_without_password(client, make_user, caplog):
    user = make_user()
    with caplog.at_level(logging.INFO, logger="audit"):
        login(client, user.email, "WrongPass1")
    text = caplog.text
    assert "login_failed" in text
    assert "WrongPass1" not in text


# ---------- access tokens ----------

def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_expired_token_rejected(client, make_user):
    user = make_user()
    s = get_settings()
    expired = jwt.encode(
        {"sub": str(user.id), "role": "CUSTOMER", "type": ACCESS,
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        s.secret_key, algorithm=s.algorithm,
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_signed_with_other_key_rejected(client, make_user):
    user = make_user()
    forged = jwt.encode(
        {"sub": str(user.id), "role": "ADMIN", "type": ACCESS,
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-key-that-is-long-enough", algorithm="HS256",
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client, make_user):
    user = make_user()
    refresh = create_refresh_token(user.id, user.role.value)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"}).status_code == 401


def test_token_for_deleted_user_rejected(client, make_user, db):
    user = make_user()
    token = create_access_token(user.id, user.role.value)
    db.delete(user)
    db.commit()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_suspending_user_blocks_existing_access_token(client, make_user, auth_headers, db):
    user = make_user()
    headers = auth_headers(user)
    assert client.get("/auth/me", headers=headers).status_code == 200
    user.status = UserStatus.SUSPENDED
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 403


# ---------- refresh ----------

def test_refresh_returns_new_working_pair(client, make_user):
    user = make_user()
    tokens = login(client, user.email).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"}).status_code == 200


def test_access_token_cannot_be_used_to_refresh(client, make_user):
    user = make_user()
    access = create_access_token(user.id, user.role.value)
    assert client.post("/auth/refresh", json={"refresh_token": access}).status_code == 401


def test_refresh_blocked_for_suspended_user(client, make_user, db):
    user = make_user()
    refresh = create_refresh_token(user.id, user.role.value)
    user.status = UserStatus.SUSPENDED
    db.commit()
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_refresh_with_garbage(client):
    assert client.post("/auth/refresh", json={"refresh_token": "nope"}).status_code == 401


# ---------- security helpers / config ----------

def test_hash_is_salted_and_verifiable():
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2
    assert verify_password("Secret123", h1) and not verify_password("Secret124", h1)
    assert not verify_password("anything", None)


def test_production_refuses_default_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="change-me-in-real-env")
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="too-short")
    assert Settings(environment="production", secret_key="x" * 40).environment == "production"


def test_login_rate_limit_returns_429(client, make_user):
    user = make_user()
    limiter.enabled = True
    try:
        limiter.reset()
        codes = [login(client, user.email, "WrongPass1").status_code for _ in range(12)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[0] == 401 and 429 in codes


# ---------- database URL handling ----------

@pytest.mark.parametrize(
    "given",
    ["postgres://u:p@host/db", "postgresql://u:p@host/db"],
)
def test_postgres_urls_use_psycopg2_driver(given):
    """Regression: SQLAlchemy 2.1 defaults postgresql:// to psycopg v3, which is not installed."""
    from app.db.database import normalize_database_url

    assert normalize_database_url(given) == "postgresql+psycopg2://u:p@host/db"


def test_other_database_urls_unchanged():
    from app.db.database import normalize_database_url

    assert normalize_database_url("sqlite:///./banking.db") == "sqlite:///./banking.db"
    assert normalize_database_url("postgresql+psycopg2://u:p@h/d") == "postgresql+psycopg2://u:p@h/d"


def test_user_with_reserved_domain_email_does_not_break_responses(client, make_user, auth_headers):
    """Regression (found on PostgreSQL): an admin created via the CLI with admin@bank.local made
    /auth/me and /admin/users fail with a 500, because output re-validated the email."""
    from app.models.enums import UserRole

    admin = make_user(role=UserRole.ADMIN, email="admin@bank.local")
    h = auth_headers(admin)
    assert client.get("/auth/me", headers=h).status_code == 200
    r = client.get("/admin/users", headers=h)
    assert r.status_code == 200 and "admin@bank.local" in [u["email"] for u in r.json()]
    assert login(client, "admin@bank.local").status_code == 200
