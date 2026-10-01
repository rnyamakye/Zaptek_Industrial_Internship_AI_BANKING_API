"""Role-based access and account-ownership rules."""
import pytest
from fastapi import HTTPException

from app.api.deps import can_access_customer, ensure_customer_access
from app.models.enums import UserRole, UserStatus


# ---------- admin endpoints: roles ----------

def test_admin_endpoints_require_login(client):
    assert client.get("/admin/users").status_code == 401


def test_customer_cannot_use_admin_endpoints(client, make_user, auth_headers):
    customer = make_user()
    h = auth_headers(customer)
    assert client.get("/admin/users", headers=h).status_code == 403
    assert client.get(f"/admin/users/{customer.id}", headers=h).status_code == 403
    assert client.patch(f"/admin/users/{customer.id}", json={"role": "ADMIN"}, headers=h).status_code == 403


def test_customer_cannot_promote_themselves(client, make_user, auth_headers, db):
    customer = make_user()
    client.patch(f"/admin/users/{customer.id}", json={"role": "ADMIN"}, headers=auth_headers(customer))
    db.refresh(customer)
    assert customer.role == UserRole.CUSTOMER


def test_staff_can_list_and_view_but_not_modify(client, make_user, auth_headers):
    staff = make_user(role=UserRole.STAFF)
    customer = make_user()
    h = auth_headers(staff)
    listing = client.get("/admin/users", headers=h)
    assert listing.status_code == 200
    assert int(listing.headers["X-Total-Count"]) == 2
    assert all("password_hash" not in u for u in listing.json())
    assert client.get(f"/admin/users/{customer.id}", headers=h).status_code == 200
    assert client.patch(f"/admin/users/{customer.id}", json={"status": "SUSPENDED"}, headers=h).status_code == 403


def test_admin_can_change_role_and_status(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    customer = make_user()
    h = auth_headers(admin)
    r = client.patch(f"/admin/users/{customer.id}", json={"role": "STAFF"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "STAFF"
    r = client.patch(f"/admin/users/{customer.id}", json={"status": "SUSPENDED"}, headers=h)
    assert r.json()["status"] == "SUSPENDED"


def test_admin_cannot_change_own_role_or_status(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    r = client.patch(f"/admin/users/{admin.id}", json={"status": "SUSPENDED"}, headers=auth_headers(admin))
    assert r.status_code == 400


def test_admin_update_unknown_user_404(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    assert client.patch("/admin/users/9999", json={"status": "SUSPENDED"}, headers=auth_headers(admin)).status_code == 404


def test_admin_update_rejects_invalid_role(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    customer = make_user()
    r = client.patch(f"/admin/users/{customer.id}", json={"role": "SUPERUSER"}, headers=auth_headers(admin))
    assert r.status_code == 422


def test_admin_list_filters_and_pagination(client, make_user, auth_headers):
    admin = make_user(role=UserRole.ADMIN)
    for _ in range(3):
        make_user()
    h = auth_headers(admin)
    r = client.get("/admin/users?role=CUSTOMER&limit=2", headers=h)
    assert len(r.json()) == 2 and r.headers["X-Total-Count"] == "3"
    assert client.get("/admin/users?limit=1000", headers=h).status_code == 422


# ---------- ownership helpers used by every banking router ----------

def test_customer_can_only_access_own_customer_id(make_user):
    a, b = make_user(), make_user()
    assert can_access_customer(a, a.profile.id)
    assert not can_access_customer(a, b.profile.id)
    with pytest.raises(HTTPException) as exc:
        ensure_customer_access(a, b.profile.id)
    assert exc.value.status_code == 404  # 404, so other customers' resources are not revealed


def test_staff_and_admin_can_access_any_customer(make_user):
    customer = make_user()
    assert can_access_customer(make_user(role=UserRole.STAFF), customer.profile.id)
    assert can_access_customer(make_user(role=UserRole.ADMIN), customer.profile.id)


# ---------- test-infrastructure guard ----------

def test_test_database_enforces_foreign_keys(db):
    """If this fails, tests would accept data that PostgreSQL rejects."""
    from datetime import date
    from sqlalchemy.exc import IntegrityError
    from app.models import CustomerProfile

    db.add(CustomerProfile(user_id=9999, date_of_birth=date(2000, 1, 1), address="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
