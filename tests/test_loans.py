from decimal import Decimal

import pytest

from app.models import Loan, Notification
from app.models.enums import UserRole


def apply(client, user, auth_headers, amount="5000.00", duration=12):
    return client.post("/loans", json={"amount": amount, "duration": duration}, headers=auth_headers(user))


def test_requires_login(client):
    assert client.get("/loans").status_code == 401
    assert client.post("/loans", json={"amount": "100", "duration": 6}).status_code == 401
    assert client.patch("/loans/1", json={"status": "APPROVED"}).status_code == 401


def test_customer_applies_status_pending_and_rate_set_by_bank(client, make_user, auth_headers):
    c = make_user()
    r = client.post("/loans", json={"amount": "5000.00", "duration": 12, "interest_rate": "0.01", "status": "APPROVED"}, headers=auth_headers(c))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDING"            # client cannot pick the status
    assert Decimal(body["interest_rate"]) == Decimal("24.00")  # nor the interest rate
    assert body["customer_id"] == c.profile.id
    assert Decimal(body["monthly_payment"]) > Decimal("5000") / 12  # interest makes it higher


@pytest.mark.parametrize("duration,rate", [(6, "24.00"), (12, "24.00"), (24, "27.00"), (36, "27.00"), (48, "30.00")])
def test_rate_bands(client, make_user, auth_headers, duration, rate):
    r = apply(client, make_user(), auth_headers, duration=duration)
    assert Decimal(r.json()["interest_rate"]) == Decimal(rate)


@pytest.mark.parametrize("change", [{"amount": "0"}, {"amount": "-5"}, {"amount": "100001"}, {"amount": "10.123"}, {"duration": 0}, {"duration": 61}])
def test_invalid_applications_rejected(client, make_user, auth_headers, change):
    body = {"amount": "1000.00", "duration": 12, **change}
    assert client.post("/loans", json=body, headers=auth_headers(make_user())).status_code == 422


def test_only_one_pending_loan_at_a_time(client, make_user, auth_headers):
    c = make_user()
    assert apply(client, c, auth_headers).status_code == 201
    assert apply(client, c, auth_headers).status_code == 409


def test_staff_cannot_apply_without_profile(client, make_user, auth_headers):
    assert apply(client, make_user(role=UserRole.STAFF), auth_headers).status_code == 403


def test_customer_sees_only_own_loans(client, make_user, auth_headers):
    a, b = make_user(), make_user()
    loan = apply(client, a, auth_headers).json()
    assert client.get("/loans", headers=auth_headers(b)).json() == []
    assert client.get(f"/loans/{loan['id']}", headers=auth_headers(b)).status_code == 404
    assert client.get(f"/loans/{loan['id']}", headers=auth_headers(a)).status_code == 200


def test_staff_sees_everything_with_filters_and_pagination(client, make_user, auth_headers):
    a, b, staff = make_user(), make_user(), make_user(role=UserRole.STAFF)
    apply(client, a, auth_headers)
    apply(client, b, auth_headers)
    h = auth_headers(staff)
    r = client.get("/loans?limit=1", headers=h)
    assert len(r.json()) == 1 and r.headers["X-Total-Count"] == "2"
    assert len(client.get(f"/loans?customer_id={a.profile.id}", headers=h).json()) == 1
    assert client.get("/loans?status=APPROVED", headers=h).json() == []
    assert client.get("/loans?limit=1000", headers=h).status_code == 422


def test_customer_cannot_decide_own_loan(client, make_user, auth_headers):
    c = make_user()
    loan = apply(client, c, auth_headers).json()
    assert client.patch(f"/loans/{loan['id']}", json={"status": "APPROVED"}, headers=auth_headers(c)).status_code == 403


def test_staff_approves_and_customer_is_notified(client, db, make_user, auth_headers):
    c, staff = make_user(), make_user(role=UserRole.STAFF)
    loan = apply(client, c, auth_headers).json()
    r = client.patch(f"/loans/{loan['id']}", json={"status": "APPROVED"}, headers=auth_headers(staff))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"
    titles = [n.title for n in db.query(Notification).filter(Notification.user_id == c.id)]
    assert "Loan approved" in titles and "Loan application received" in titles


def test_decision_only_allowed_once_and_validated(client, make_user, auth_headers):
    c, staff = make_user(), make_user(role=UserRole.STAFF)
    loan = apply(client, c, auth_headers).json()
    h = auth_headers(staff)
    assert client.patch(f"/loans/{loan['id']}", json={"status": "PENDING"}, headers=h).status_code == 422
    assert client.patch(f"/loans/{loan['id']}", json={"status": "REJECTED"}, headers=h).status_code == 200
    assert client.patch(f"/loans/{loan['id']}", json={"status": "APPROVED"}, headers=h).status_code == 400
    assert client.patch("/loans/9999", json={"status": "APPROVED"}, headers=h).status_code == 404


def test_new_application_allowed_after_decision(client, make_user, auth_headers):
    c, staff = make_user(), make_user(role=UserRole.STAFF)
    loan = apply(client, c, auth_headers).json()
    client.patch(f"/loans/{loan['id']}", json={"status": "REJECTED"}, headers=auth_headers(staff))
    assert apply(client, c, auth_headers).status_code == 201


def test_monthly_payment_formula(client, make_user, auth_headers):
    """GHS 12,000 over 12 months at 24%/year -> standard amortised payment 1134.72."""
    r = apply(client, make_user(), auth_headers, amount="12000.00", duration=12)
    assert Decimal(r.json()["monthly_payment"]) == Decimal("1134.72")
