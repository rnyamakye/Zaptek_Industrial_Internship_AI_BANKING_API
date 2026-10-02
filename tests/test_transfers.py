"""Transfers API tests. Owner: Banasco."""

from app.models.account import Account
from decimal import Decimal
from app.models.beneficiary import Beneficiary
from app.models.enums import (
    AccountStatus,
    BeneficiaryStatus,
    UserRole,
)



def create_account(client, user, auth_headers, currency="GHS"):
    return client.post(
        "/accounts",
        json={
            "account_type": "SAVINGS",
            "currency": currency,
        },
        headers=auth_headers(user),
    )


def create_beneficiary(db, customer, name="Test Beneficiary"):
    beneficiary = Beneficiary(
        customer_id=customer.profile.id,
        name=name,
        account_number="0123456789",
        bank_name="Test Bank",
        status=BeneficiaryStatus.ACTIVE,
    )
    db.add(beneficiary)
    db.commit()
    db.refresh(beneficiary)
    return beneficiary


def create_transfer(
    client,
    user,
    auth_headers,
    sender_account_id,
    beneficiary_id,
    amount="100.00",
    reference="TRANSFER-001",
):
    return client.post(
        "/transfers",
        json={
            "sender_account_id": sender_account_id,
            "beneficiary_id": beneficiary_id,
            "amount": amount,
            "reference": reference,
        },
        headers=auth_headers(user),
    )


def fund_account(db, account, amount="1000.00"):
    account.balance = Decimal(amount)
    db.commit()
    db.refresh(account)



# ---------- authentication ----------


def test_transfers_require_login(client):
    assert client.get(
        "/transfers",
        params={"account_id": 1},
    ).status_code == 401

    assert client.post(
        "/transfers",
        json={
            "sender_account_id": 1,
            "beneficiary_id": 1,
            "amount": "100.00",
            "reference": "TRANSFER-001",
        },
    ).status_code == 401


# ---------- create ----------


def test_customer_can_create_transfer(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sender_account_id"] == account_id
    assert data["beneficiary_id"] == beneficiary.id
    assert data["amount"] == "100.00"
    assert data["reference"] == "TRANSFER-001"
    assert data["status"] == "COMPLETED"


def test_transfer_deducts_sender_balance(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account, "1000.00")

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
        amount="250.00",
        reference="TRANSFER-BALANCE-001",
    )

    assert response.status_code == 201

    db.refresh(account)

    assert str(account.balance) == "750.00"


def test_transfer_is_created_as_completed(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
        reference="TRANSFER-STATUS-001",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETED"


def test_customer_cannot_create_transfer_from_another_customers_account(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer_a)

    response = create_transfer(
        client,
        customer_a,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    assert response.status_code == 404


def test_staff_can_create_transfer_from_any_account(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        staff,
        auth_headers,
        account_id,
        beneficiary.id,
        reference="TRANSFER-STAFF-001",
    )

    assert response.status_code == 201


def test_admin_can_create_transfer_from_any_account(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        admin,
        auth_headers,
        account_id,
        beneficiary.id,
        reference="TRANSFER-ADMIN-001",
    )

    assert response.status_code == 201


def test_unknown_sender_account_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = create_transfer(
        client,
        customer,
        auth_headers,
        999999,
        1,
    )

    assert response.status_code == 404


def test_unknown_beneficiary_returns_400(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        999999,
    )

    assert response.status_code == 400
    assert "beneficiary" in response.json()["detail"].lower()


def test_inactive_sender_account_is_rejected(
    client,
    db,
    make_user,
    auth_headers,
):
    from app.models.account import Account

    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )
    account_id = account_response.json()["id"]

    account = db.get(Account, account_id)
    fund_account(db, account)
    account.status = AccountStatus.FROZEN
    db.commit()

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    assert response.status_code == 400
    assert "not active" in response.json()["detail"].lower()


def test_inactive_beneficiary_is_rejected(
    client,
    db,
    make_user,
    auth_headers,
):
    from app.models.account import Account

    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )
    account_id = account_response.json()["id"]

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)
    beneficiary.status = BeneficiaryStatus.INACTIVE
    db.commit()

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    assert response.status_code == 400
    assert "beneficiary" in response.json()["detail"].lower()


def test_transfer_rejects_insufficient_balance(
    client,
    db,
    make_user,
    auth_headers,
):
    from app.models.account import Account

    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )
    account_id = account_response.json()["id"]

    account = db.get(Account, account_id)
    fund_account(db, account, "50.00")

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
        amount="100.00",
    )

    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


def test_transfer_rejects_invalid_amount(
    client,
    db,
    make_user,
    auth_headers,
):
    from app.models.account import Account

    customer = make_user()

    account_response = create_account(
        client,
        customer,
        auth_headers,
    )
    account_id = account_response.json()["id"]

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    response = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
        amount="0",
    )

    assert response.status_code == 422


# ---------- get by id ----------


def test_customer_can_get_own_transfer(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    created = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    transfer_id = created.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert response.json()["id"] == transfer_id


def test_customer_cannot_get_another_customers_transfer(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer_b)

    created = create_transfer(
        client,
        customer_b,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    transfer_id = created.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_get_any_transfer(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    created = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    transfer_id = created.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200


def test_admin_can_get_any_transfer(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    created = create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    transfer_id = created.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200


def test_unknown_transfer_returns_404(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/transfers/999999",
        headers=auth_headers(customer),
    )

    assert response.status_code == 404


# ---------- list ----------


def test_customer_can_list_own_transfers(
    client,
    db,
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

    account = db.get(Account, account_id)
    fund_account(db, account, "1000.00")

    beneficiary = create_beneficiary(db, customer)

    create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
        amount="100.00",
        reference="TRANSFER-LIST-001",
    )

    response = client.get(
        "/transfers",
        params={"account_id": account_id},
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "1"


def test_customer_cannot_list_another_customers_transfers(
    client,
    db,
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

    account = db.get(__import__("app.models.account", fromlist=["Account"]).Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer_b)

    create_transfer(
        client,
        customer_b,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    response = client.get(
        "/transfers",
        params={"account_id": account_id},
        headers=auth_headers(customer_a),
    )

    assert response.status_code == 404


def test_staff_can_list_any_customer_transfers(
    client,
    db,
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

    account = db.get(__import__("app.models.account", fromlist=["Account"]).Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    response = client.get(
        "/transfers",
        params={"account_id": account_id},
        headers=auth_headers(staff),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_admin_can_list_any_customer_transfers(
    client,
    db,
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

    account = db.get(__import__("app.models.account", fromlist=["Account"]).Account, account_id)
    fund_account(db, account)

    beneficiary = create_beneficiary(db, customer)

    create_transfer(
        client,
        customer,
        auth_headers,
        account_id,
        beneficiary.id,
    )

    response = client.get(
        "/transfers",
        params={"account_id": account_id},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_transfer_pagination_and_total_count(
    client,
    db,
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

    account = db.get(__import__("app.models.account", fromlist=["Account"]).Account, account_id)
    fund_account(db, account, "1000.00")

    beneficiary = create_beneficiary(db, customer)

    for i in range(3):
        create_transfer(
            client,
            customer,
            auth_headers,
            account_id,
            beneficiary.id,
            amount="10.00",
            reference=f"TRANSFER-PAGE-{i}",
        )

    response = client.get(
        "/transfers",
        params={
            "account_id": account_id,
            "skip": 1,
            "limit": 1,
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["X-Total-Count"] == "3"


def test_transfer_invalid_limit_returns_422(
    client,
    make_user,
    auth_headers,
):
    customer = make_user()

    response = client.get(
        "/transfers",
        params={
            "account_id": 1,
            "limit": 101,
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 422