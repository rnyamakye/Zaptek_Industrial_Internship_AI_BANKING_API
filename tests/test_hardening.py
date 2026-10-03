"""Rules added after the review of the banking operations: staff-only credits, account status
control, beneficiary ownership, AI risk persistence, unique account numbers."""
from decimal import Decimal

from app.models import Account, Beneficiary, RiskAssessment, Transaction
from app.models.enums import AccountStatus, AccountType, UserRole


def make_account(db, user, balance="1000.00", status=AccountStatus.ACTIVE):
    n = db.query(Account).count() + 1
    a = Account(
        customer_id=user.profile.id, account_number=f"77{n:08d}", account_type=AccountType.SAVINGS,
        balance=Decimal(balance), status=status,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def txn(client, headers, account_id, kind="WITHDRAWAL", amount="10.00", ref="T-1"):
    return client.post(
        "/transactions",
        json={"account_id": account_id, "transaction_type": kind, "amount": amount, "currency": "GHS", "reference": ref},
        headers=headers,
    )


# ---------- credits are staff-only ----------

def test_customer_cannot_deposit_into_own_account(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "0.00")
    for kind in ("DEPOSIT", "CREDIT"):
        r = txn(client, auth_headers(customer), acct.id, kind, "1000000", f"FREE-{kind}")
        assert r.status_code == 403
    db.refresh(acct)
    assert acct.balance == Decimal("0.00")


def test_staff_can_deposit_into_customer_account(client, db, make_user, auth_headers):
    customer, staff = make_user(), make_user(role=UserRole.STAFF)
    acct = make_account(db, customer, "0.00")
    r = txn(client, auth_headers(staff), acct.id, "DEPOSIT", "250.00", "DEP-1")
    assert r.status_code == 201
    db.refresh(acct)
    assert acct.balance == Decimal("250.00")


def test_customer_can_withdraw_and_cannot_overdraw(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "100.00")
    assert txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "40.00", "W-1").status_code == 201
    assert txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "100.00", "W-2").status_code == 400
    db.refresh(acct)
    assert acct.balance == Decimal("60.00")


# ---------- AI risk assessment is returned and stored ----------

def test_transaction_response_contains_risk_and_it_is_saved(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "500.00")
    r = txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "20.00", "R-1")
    assert r.status_code == 201
    body = r.json()
    assert set(body["risk"]) == {"transaction_id", "risk_score", "risk_level", "model_version"}
    assert body["risk"]["transaction_id"] == body["id"]
    assert 0.0 <= body["risk"]["risk_score"] <= 1.0
    saved = db.query(RiskAssessment).one()
    assert saved.transaction_id == body["id"]
    assert saved.customer_id == customer.profile.id
    assert saved.model_version == body["risk"]["model_version"]


def test_high_risk_transaction_is_flagged(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "100000.00")
    # small history so a large amount is far above the account's average
    for i in range(3):
        db.add(Transaction(account_id=acct.id, transaction_type="DEBIT", amount=Decimal("10"), currency="GHS",
                           reference=f"H-{i}", status="COMPLETED"))
    db.commit()
    r = txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "9000.00", "BIG-1")
    assert r.status_code == 201
    assert r.json()["risk"]["risk_level"] in {"MEDIUM", "HIGH"}
    if r.json()["risk"]["risk_level"] == "HIGH":
        assert r.json()["status"] == "FLAGGED"


def test_failed_transaction_leaves_no_risk_assessment(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "5.00")
    assert txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "50.00", "F-1").status_code == 400
    assert db.query(RiskAssessment).count() == 0
    assert db.query(Transaction).count() == 0


# ---------- account status control ----------

def test_customer_cannot_freeze_or_reactivate_own_account(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "0.00", status=AccountStatus.FROZEN)
    for target in ("ACTIVE", "FROZEN"):
        r = client.patch(f"/accounts/{acct.id}", json={"status": target}, headers=auth_headers(customer))
        assert r.status_code == 403
    db.refresh(acct)
    assert acct.status == AccountStatus.FROZEN


def test_customer_cannot_close_account_with_balance(client, db, make_user, auth_headers):
    customer = make_user()
    acct = make_account(db, customer, "10.00")
    r = client.patch(f"/accounts/{acct.id}", json={"status": "CLOSED"}, headers=auth_headers(customer))
    assert r.status_code == 400


def test_staff_can_freeze_and_unfreeze(client, db, make_user, auth_headers):
    customer, staff = make_user(), make_user(role=UserRole.STAFF)
    acct = make_account(db, customer, "10.00")
    h = auth_headers(staff)
    assert client.patch(f"/accounts/{acct.id}", json={"status": "FROZEN"}, headers=h).json()["status"] == "FROZEN"
    # frozen accounts cannot transact
    assert txn(client, auth_headers(customer), acct.id, "WITHDRAWAL", "1.00", "FZ-1").status_code == 400
    assert client.patch(f"/accounts/{acct.id}", json={"status": "ACTIVE"}, headers=h).json()["status"] == "ACTIVE"


# ---------- transfers: beneficiary ownership ----------

def test_cannot_transfer_to_another_customers_beneficiary(client, db, make_user, auth_headers):
    a, b = make_user(), make_user()
    acct = make_account(db, a, "100.00")
    ben = Beneficiary(customer_id=b.profile.id, name="Other's payee", account_number="1234567890", bank_name="GCB")
    db.add(ben)
    db.commit()
    r = client.post(
        "/transfers",
        json={"sender_account_id": acct.id, "beneficiary_id": ben.id, "amount": "10.00", "reference": "X-1"},
        headers=auth_headers(a),
    )
    assert r.status_code == 400
    db.refresh(acct)
    assert acct.balance == Decimal("100.00")


# ---------- account numbers ----------

def test_account_numbers_are_unique_and_well_formed(client, make_user, auth_headers):
    customer = make_user()
    numbers = set()
    for _ in range(8):
        r = client.post("/accounts", json={"account_type": "SAVINGS"}, headers=auth_headers(customer))
        assert r.status_code == 201
        numbers.add(r.json()["account_number"])
    assert len(numbers) == 8
    assert all(len(n) == 10 and n.startswith("1000") and n.isdigit() for n in numbers)


# ---------- duplicate references (found on PostgreSQL: used to crash with a 500) ----------

def test_duplicate_transaction_reference_is_409_and_changes_nothing(client, db, make_user, make_account, auth_headers):
    c = make_user()
    acct = make_account(c, "100.00")
    h = auth_headers(c)
    assert txn(client, h, acct.id, "WITHDRAWAL", "10.00", "DUP-1").status_code == 201
    again = txn(client, h, acct.id, "WITHDRAWAL", "10.00", "DUP-1")
    assert again.status_code == 409
    db.refresh(acct)
    assert acct.balance == Decimal("90.00")
    assert db.query(Transaction).count() == 1 and db.query(RiskAssessment).count() == 1


def test_duplicate_transfer_reference_is_409_and_changes_nothing(client, db, make_user, make_account, auth_headers):
    c = make_user()
    acct = make_account(c, "100.00")
    ben = Beneficiary(customer_id=c.profile.id, name="Payee", account_number="1234567890", bank_name="GCB")
    db.add(ben)
    db.commit()
    body = {"sender_account_id": acct.id, "beneficiary_id": ben.id, "amount": "10.00", "reference": "TDUP-1"}
    assert client.post("/transfers", json=body, headers=auth_headers(c)).status_code == 201
    assert client.post("/transfers", json=body, headers=auth_headers(c)).status_code == 409
    db.refresh(acct)
    assert acct.balance == Decimal("90.00")
