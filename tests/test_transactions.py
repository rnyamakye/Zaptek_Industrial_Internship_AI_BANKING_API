"""Transactions API tests. Owner: Banasco."""



from app.models.enums import UserRole


def create_account(client, user, auth_headers, currency="GHS"):
    return client.post(
        "/accounts",
        json={
            "account_type": "SAVINGS",
            "currency": currency,
        },
        headers=auth_headers(user),
    )


def _teller_for(user):
    """Deposits/credits are staff-only, so tests that need money in an account post them as staff."""
    from sqlalchemy.orm import object_session

    from app.models import User
    from app.models.enums import UserRole, UserStatus

    db = object_session(user)
    email = f"teller{user.id}@example.com"
    teller = db.query(User).filter(User.email == email).first()
    if teller is None:
        teller = User(
            full_name="Teller", email=email, phone=f"0200{user.id:06d}",
            password_hash="x", role=UserRole.STAFF, status=UserStatus.ACTIVE,
        )
        db.add(teller)
        db.commit()
    return teller


def create_transaction(
    client,
    user,
    auth_headers,
    account_id,
    amount="100.00",
    transaction_type="DEPOSIT",
    currency="GHS",
    reference="TXN-001",
):
    if transaction_type in ("DEPOSIT", "CREDIT") and user.role.value == "CUSTOMER":
        user = _teller_for(user)
    return client.post(
        "/transactions",
        json={
            "account_id": account_id,
            "transaction_type": transaction_type,
            "amount": amount,
            "currency": currency,
            "reference": reference,
        },
        headers=auth_headers(user),
    )


# ---------- authentication ----------


def test_transactions_require_login(client):
    assert client.get("/transactions").status_code == 401

    assert client.post(
        "/transactions",
        json={
            "account_id": 1,
            "transaction_type": "DEPOSIT",
            "amount": "100.00",
            "currency": "GHS",
            "reference": "TXN-001",
        },
    ).status_code == 401


# ---------- create ----------


def test_deposit_creates_transaction(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["account_id"] == account_id
    assert data["transaction_type"] == "DEPOSIT"
    assert data["amount"] == "100.00"
    assert data["currency"] == "GHS"
    assert data["reference"] == "TXN-001"
    assert data["status"] in {"COMPLETED", "FLAGGED"}


def test_customer_cannot_create_transaction_on_another_customers_account(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    account_response = create_account(
        client,
        customer_b,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        customer_a,
        auth_headers,
        account_id,
        transaction_type="WITHDRAWAL",
    )

    assert response.status_code == 404


def test_staff_can_create_transaction_on_any_account(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        staff,
        auth_headers,
        account_id,
    )

    assert response.status_code == 201


def test_admin_can_create_transaction_on_any_account(
    client,
    make_user,
    auth_headers,
):
    admin = make_user(role=UserRole.ADMIN)
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        admin,
        auth_headers,
        account_id,
    )

    assert response.status_code == 201


def test_unknown_account_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = create_transaction(
        client,
        customer,
        auth_headers,
        999999,
    )

    assert response.status_code == 404


def test_transaction_rejects_invalid_amount(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
        amount="0",
    )

    assert response.status_code == 422


def test_transaction_currency_must_match_account(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
        currency="GHS",
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
        currency="USD",
    )

    assert response.status_code == 400
    assert "currency" in response.json()["detail"].lower()


def test_withdrawal_cannot_exceed_balance(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
        amount="100.00",
        transaction_type="WITHDRAWAL",
    )

    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


# ---------- get by id ----------


def test_customer_can_get_own_transaction(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    created = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
    )

    transaction_id = created.json()["id"]

    response = client.get(
        f"/transactions/{transaction_id}",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.json()["id"] == transaction_id


def test_customer_cannot_get_another_customers_transaction(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    account_response = create_account(
        client,
        customer_b,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    created = create_transaction(
        client,
        customer_b,
        auth_headers,
        account_id,
    )

    transaction_id = created.json()["id"]

    response = client.get(
        f"/transactions/{transaction_id}",
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_get_any_transaction(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    created = create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
    )

    transaction_id = created.json()["id"]

    response = client.get(
        f"/transactions/{transaction_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200


def test_unknown_transaction_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/transactions/999999",
        headers=auth_headers(customer),
    )

    assert response.status_code == 404


# ---------- list ----------


def test_customer_can_list_transactions_for_own_account(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
        reference="TXN-001",
    )

    create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
        reference="TXN-002",
    )

    response = client.get(
        f"/transactions?account_id={account_id}",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.json()) == 2


def test_customer_cannot_list_another_customers_transactions(
    client,
    make_user,
    auth_headers,
):
    customer_a = make_user()
    customer_b = make_user()

    account_response = create_account(
        client,
        customer_b,
        auth_headers,
    )

    account_id = account_response.json()["id"]

    response = client.get(
        f"/transactions?account_id={account_id}",
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_list_all_transactions(
    client,
    make_user,
    auth_headers,
):
    staff = make_user(role=UserRole.STAFF)
    customer_a = make_user()
    customer_b = make_user()

    account_a = create_account(
        client,
        customer_a,
        auth_headers,
    ).json()["id"]

    account_b = create_account(
        client,
        customer_b,
        auth_headers,
    ).json()["id"]

    create_transaction(
        client,
        customer_a,
        auth_headers,
        account_a,
        reference="TXN-001",
    )

    create_transaction(
        client,
        customer_b,
        auth_headers,
        account_b,
        reference="TXN-002",
    )

    response = client.get(
        "/transactions",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert len(response.json()) == 2


def test_admin_can_list_all_transactions(
    client,
    make_user,
    auth_headers,
):
    admin = make_user(role=UserRole.ADMIN)
    customer = make_user()

    account_id = create_account(
        client,
        customer,
        auth_headers,
    ).json()["id"]

    create_transaction(
        client,
        customer,
        auth_headers,
        account_id,
    )

    response = client.get(
        "/transactions",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    assert len(response.json()) == 1


def test_customer_cannot_list_all_transactions_without_account_filter(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/transactions",
        headers=auth_headers(customer),
    )

    assert response.status_code == 404


def test_transaction_list_pagination(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_id = create_account(
        client,
        customer,
        auth_headers,
    ).json()["id"]

    for index in range(3):
        create_transaction(
            client,
            customer,
            auth_headers,
            account_id,
            reference=f"TXN-{index}",
        )

    response = client.get(
        f"/transactions?account_id={account_id}&skip=1&limit=1",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "3"
    assert len(response.json()) == 1


def test_transaction_list_rejects_invalid_limit(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    account_id = create_account(
        client,
        customer,
        auth_headers,
    ).json()["id"]

    response = client.get(
        f"/transactions?account_id={account_id}&limit=101",
        headers=auth_headers(customer),
    )

    assert response.status_code == 422