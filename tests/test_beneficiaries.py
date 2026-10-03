from app.models import Beneficiary
from app.models.enums import BeneficiaryStatus, UserRole

PAYLOAD = {"name": "Kofi Owusu", "account_number": "0123456789", "bank_name": "GCB Bank"}


def add(client, user, auth_headers, **over):
    return client.post("/beneficiaries", json={**PAYLOAD, **over}, headers=auth_headers(user))


def test_requires_login(client):
    assert client.get("/beneficiaries").status_code == 401
    assert client.post("/beneficiaries", json=PAYLOAD).status_code == 401
    assert client.delete("/beneficiaries/1").status_code == 401


def test_customer_creates_and_lists_own(client, make_user, auth_headers):
    c = make_user()
    r = add(client, c, auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["customer_id"] == c.profile.id and body["status"] == "ACTIVE"
    listing = client.get("/beneficiaries", headers=auth_headers(c))
    assert listing.status_code == 200 and len(listing.json()) == 1
    assert listing.headers["X-Total-Count"] == "1"


def test_duplicate_is_409(client, make_user, auth_headers):
    c = make_user()
    assert add(client, c, auth_headers).status_code == 201
    assert add(client, c, auth_headers).status_code == 409


def test_same_account_allowed_for_different_customers(client, make_user, auth_headers):
    assert add(client, make_user(), auth_headers).status_code == 201
    assert add(client, make_user(), auth_headers).status_code == 201


def test_staff_cannot_create_beneficiary_without_profile(client, make_user, auth_headers):
    assert add(client, make_user(role=UserRole.STAFF), auth_headers).status_code == 403


import pytest


@pytest.mark.parametrize("change", [{"account_number": "12ab"}, {"account_number": "123"}, {"name": "K"}, {"bank_name": ""}])
def test_invalid_input_is_422(client, make_user, auth_headers, change):
    assert add(client, make_user(), auth_headers, **change).status_code == 422


def test_customer_never_sees_other_customers_beneficiaries(client, make_user, auth_headers):
    a, b = make_user(), make_user()
    created = add(client, a, auth_headers).json()
    assert client.get("/beneficiaries", headers=auth_headers(b)).json() == []
    assert client.delete(f"/beneficiaries/{created['id']}", headers=auth_headers(b)).status_code == 404


def test_staff_sees_all_and_can_filter(client, make_user, auth_headers):
    a, b, staff = make_user(), make_user(), make_user(role=UserRole.STAFF)
    add(client, a, auth_headers)
    add(client, b, auth_headers, account_number="9999999999")
    h = auth_headers(staff)
    assert len(client.get("/beneficiaries", headers=h).json()) == 2
    assert len(client.get(f"/beneficiaries?customer_id={a.profile.id}", headers=h).json()) == 1


def test_delete_is_soft_and_idempotent(client, db, make_user, auth_headers):
    c = make_user()
    bid = add(client, c, auth_headers).json()["id"]
    assert client.delete(f"/beneficiaries/{bid}", headers=auth_headers(c)).status_code == 204
    assert client.delete(f"/beneficiaries/{bid}", headers=auth_headers(c)).status_code == 204
    assert db.get(Beneficiary, bid).status == BeneficiaryStatus.INACTIVE  # row kept for transfer history
    assert client.get("/beneficiaries", headers=auth_headers(c)).json() == []
    assert len(client.get("/beneficiaries?status=INACTIVE", headers=auth_headers(c)).json()) == 1


def test_beneficiary_with_transfers_can_be_removed(client, db, make_user, make_account, auth_headers):
    """A hard delete would violate the foreign key from transfers; the soft delete must not."""
    c = make_user()
    acct = make_account(c, "100.00")
    bid = add(client, c, auth_headers).json()["id"]
    t = client.post("/transfers", json={"sender_account_id": acct.id, "beneficiary_id": bid, "amount": "5.00", "reference": "B-1"}, headers=auth_headers(c))
    assert t.status_code == 201
    assert client.delete(f"/beneficiaries/{bid}", headers=auth_headers(c)).status_code == 204


def test_removed_beneficiary_cannot_receive_transfers_but_can_be_restored(client, make_user, make_account, auth_headers):
    c = make_user()
    acct = make_account(c, "100.00")
    bid = add(client, c, auth_headers).json()["id"]
    client.delete(f"/beneficiaries/{bid}", headers=auth_headers(c))
    body = {"sender_account_id": acct.id, "beneficiary_id": bid, "amount": "5.00", "reference": "B-2"}
    assert client.post("/transfers", json=body, headers=auth_headers(c)).status_code == 400
    restored = add(client, c, auth_headers, name="Kofi O.")
    assert restored.status_code == 201 and restored.json()["id"] == bid and restored.json()["status"] == "ACTIVE"
    assert client.post("/transfers", json={**body, "reference": "B-3"}, headers=auth_headers(c)).status_code == 201


def test_delete_unknown_is_404(client, make_user, auth_headers):
    assert client.delete("/beneficiaries/9999", headers=auth_headers(make_user())).status_code == 404
