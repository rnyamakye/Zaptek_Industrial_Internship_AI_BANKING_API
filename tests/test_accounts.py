"""Accounts API tests. Owner: Banasco."""

from decimal import Decimal

from app.models.account import Account
from app.models.enums import AccountStatus, AccountType, UserRole


def create_account(client, user, auth_headers, account_type="SAVINGS", currency="GHS"):
    return client.post(
        "/accounts",
        json={
            "account_type": account_type,
            "currency": currency,
        },
        headers=auth_headers(user),
    )


# ---------- authentication ----------


def test_accounts_require_login(client):
    assert client.get("/accounts").status_code == 401
    assert client.post(
        "/accounts",
        json={"account_type": "SAVINGS", "currency": "GHS"},
    ).status_code == 401


# ---------- create ----------


def test_customer_can_create_account(client, make_user, auth_headers):
    customer = make_user()

    response = create_account(
        client,
        customer,
        auth_headers,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["customer_id"] == customer.profile.id
    assert data["account_type"] == "SAVINGS"
    assert data["currency"] == "GHS"
    assert data["balance"] == "0.00"
    assert data["status"] == "ACTIVE"
    assert data["account_number"].startswith("1000")


def test_account_creation_does_not_accept_customer_id(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.post(
        "/accounts",
        json={
            "customer_id": 9999,
            "account_type": "SAVINGS",
            "currency": "GHS",
        },
        headers=auth_headers(customer),
    )

    # Extra fields are ignored by Pydantic's default configuration.
    # The account must still belong to the authenticated customer.
    assert response.status_code == 201
    assert response.json()["customer_id"] == customer.profile.id


def test_non_customer_cannot_create_account(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)

    response = create_account(
        client,
        staff,
        auth_headers,
    )

    assert response.status_code == 404


# ---------- list ----------


def test_customer_only_sees_own_accounts(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    create_account(client, customer_a, auth_headers)
    create_account(client, customer_a, auth_headers)
    create_account(client, customer_b, auth_headers)

    response = client.get(
        "/accounts",
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"

    accounts = response.json()

    assert len(accounts) == 2
    assert all(
        account["customer_id"] == customer_a.profile.id
        for account in accounts
    )


def test_staff_can_list_all_accounts(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer_a = make_user()
    customer_b = make_user()

    create_account(client, customer_a, auth_headers)
    create_account(client, customer_b, auth_headers)

    response = client.get(
        "/accounts",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.json()) == 2


def test_admin_can_list_all_accounts(
    client,
    make_user,
    auth_headers,
):
    admin = make_user(role=UserRole.ADMIN)
    customer_a = make_user()
    customer_b = make_user()

    create_account(client, customer_a, auth_headers)
    create_account(client, customer_b, auth_headers)

    response = client.get(
        "/accounts",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.json()) == 2


# ---------- pagination ----------


def test_account_list_pagination(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    for _ in range(3):
        create_account(client, customer, auth_headers)

    response = client.get(
        "/accounts?skip=1&limit=1",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "3"
    assert len(response.json()) == 1


def test_account_list_rejects_invalid_limit(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/accounts?limit=101",
        headers=auth_headers(customer),
    )

    assert response.status_code == 422


# ---------- get by id ----------


def test_customer_can_get_own_account(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    created = create_account(client, customer, auth_headers)
    account_id = created.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.json()["id"] == account_id


def test_customer_cannot_get_another_customers_account(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    created = create_account(client, customer_b, auth_headers)
    account_id = created.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_get_any_account(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer = make_user()

    created = create_account(client, customer, auth_headers)
    account_id = created.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200


def test_unknown_account_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/accounts/999999",
        headers=auth_headers(customer),
    )

    assert response.status_code == 404


# ---------- update ----------


def test_customer_can_close_own_empty_account(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    created = create_account(client, customer, auth_headers)
    account_id = created.json()["id"]

    response = client.patch(
        f"/accounts/{account_id}",
        json={"status": "CLOSED"},
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def test_customer_cannot_update_another_customers_account(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    created = create_account(client, customer_b, auth_headers)
    account_id = created.json()["id"]

    response = client.patch(
        f"/accounts/{account_id}",
        json={"status": "FROZEN"},
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_update_any_account(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer = make_user()

    created = create_account(client, customer, auth_headers)
    account_id = created.json()["id"]

    response = client.patch(
        f"/accounts/{account_id}",
        json={"status": "FROZEN"},
        headers=auth_headers(staff),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "FROZEN"


def test_update_unknown_account_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.patch(
        "/accounts/999999",
        json={"status": "FROZEN"},
        headers=auth_headers(customer),
    )

    assert response.status_code == 404


def test_update_rejects_invalid_status(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    created = create_account(client, customer, auth_headers)
    account_id = created.json()["id"]

    response = client.patch(
        f"/accounts/{account_id}",
        json={"status": "INVALID"},
        headers=auth_headers(customer),
    )

    assert response.status_code == 422