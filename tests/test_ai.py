"""AI endpoints, risk integration in transactions/transfers, and model-failure handling."""
from decimal import Decimal

import pytest

from app.models import Account, Beneficiary, Notification, RiskAssessment, Transaction
from app.models.enums import RiskLevel, UserRole
from app.services.transaction_service import risk_service


class FixedModel:
    def __init__(self, score, version="test-1.0"):
        self.score, self.version = score, version

    def predict_score(self, features):
        return self.score


class BrokenModel:
    version = "broken"

    def predict_score(self, features):
        raise RuntimeError("model crashed")


def withdraw(client, headers, account_id, amount="10.00", ref="W-1"):
    return client.post(
        "/transactions",
        json={"account_id": account_id, "transaction_type": "WITHDRAWAL", "amount": amount, "currency": "GHS", "reference": ref},
        headers=headers,
    )


def beneficiary(db, user):
    b = Beneficiary(customer_id=user.profile.id, name="Payee", account_number="1234567890", bank_name="GCB")
    db.add(b)
    db.commit()
    return b


# ---------- risk in the transaction flow ----------

def test_high_risk_withdrawal_is_flagged_saved_and_notified(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.95))
    c = make_user()
    acct = make_account(c, "500.00")
    r = withdraw(client, auth_headers(c), acct.id, "100.00")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "FLAGGED"
    assert body["risk"] == {"transaction_id": body["id"], "risk_score": 0.95, "risk_level": "HIGH", "model_version": "test-1.0"}
    db.refresh(acct)
    assert acct.balance == Decimal("400.00")  # funds are held while staff review
    assert db.query(RiskAssessment).one().risk_level == RiskLevel.HIGH
    assert [n.title for n in db.query(Notification).filter(Notification.user_id == c.id)] == ["Transaction flagged for review"]


def test_low_risk_transaction_completes_without_notification(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.10))
    c = make_user()
    r = withdraw(client, auth_headers(c), make_account(c).id)
    assert r.json()["status"] == "COMPLETED" and r.json()["risk"]["risk_level"] == "LOW"
    assert db.query(Notification).count() == 0


@pytest.mark.parametrize("score,level", [(0.0, "LOW"), (0.39, "LOW"), (0.40, "MEDIUM"), (0.69, "MEDIUM"), (0.70, "HIGH"), (1.0, "HIGH")])
def test_risk_level_thresholds(client, make_user, make_account, auth_headers, monkeypatch, score, level):
    monkeypatch.setattr(risk_service, "_model", FixedModel(score))
    c = make_user()
    assert withdraw(client, auth_headers(c), make_account(c).id).json()["risk"]["risk_level"] == level


def test_model_failure_does_not_block_transaction(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", BrokenModel())
    c = make_user()
    r = withdraw(client, auth_headers(c), make_account(c).id)
    assert r.status_code == 201
    assert r.json()["risk"]["model_version"] == "rules-0.1"  # fell back to the rules
    assert db.query(Transaction).count() == 1


@pytest.mark.parametrize("bad", [float("nan"), 1.7, -0.2])
def test_invalid_model_output_is_rejected_and_fallback_used(client, make_user, make_account, auth_headers, monkeypatch, bad):
    monkeypatch.setattr(risk_service, "_model", FixedModel(bad))
    c = make_user()
    r = withdraw(client, auth_headers(c), make_account(c).id)
    assert r.status_code == 201
    assert 0.0 <= r.json()["risk"]["risk_score"] <= 1.0 and r.json()["risk"]["model_version"] == "rules-0.1"


# ---------- risk in the transfer flow ----------

def test_high_risk_transfer_is_flagged_and_stored(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.9))
    c = make_user()
    acct = make_account(c, "300.00")
    b = beneficiary(db, c)
    r = client.post("/transfers", json={"sender_account_id": acct.id, "beneficiary_id": b.id, "amount": "50.00", "reference": "T-1"}, headers=auth_headers(c))
    assert r.status_code == 201
    assert r.json()["status"] == "FLAGGED" and r.json()["risk"]["risk_level"] == "HIGH"
    db.refresh(acct)
    assert acct.balance == Decimal("250.00")
    saved = db.query(RiskAssessment).one()
    assert saved.transaction_id is None and saved.customer_id == c.profile.id
    assert db.query(Notification).filter(Notification.title == "Transfer flagged for review").count() == 1


def test_low_risk_transfer_completes(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.1))
    c = make_user()
    acct = make_account(c, "300.00")
    b = beneficiary(db, c)
    r = client.post("/transfers", json={"sender_account_id": acct.id, "beneficiary_id": b.id, "amount": "50.00", "reference": "T-2"}, headers=auth_headers(c))
    assert r.json()["status"] == "COMPLETED"


def test_failed_transfer_leaves_no_risk_assessment_or_notification(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.95))
    c = make_user()
    acct = make_account(c, "10.00")
    b = beneficiary(db, c)
    r = client.post("/transfers", json={"sender_account_id": acct.id, "beneficiary_id": b.id, "amount": "50.00", "reference": "T-3"}, headers=auth_headers(c))
    assert r.status_code == 400
    assert db.query(RiskAssessment).count() == 0 and db.query(Notification).count() == 0


def test_new_beneficiary_feature_is_true_first_time_only(client, db, make_user, make_account, auth_headers, monkeypatch):
    seen = []

    class Spy:
        version = "spy"

        def predict_score(self, f):
            seen.append(f["is_new_beneficiary"])
            return 0.1

    monkeypatch.setattr(risk_service, "_model", Spy())
    c = make_user()
    acct = make_account(c, "500.00")
    b = beneficiary(db, c)
    for i in range(2):
        client.post("/transfers", json={"sender_account_id": acct.id, "beneficiary_id": b.id, "amount": "5.00", "reference": f"S-{i}"}, headers=auth_headers(c))
    assert seen == [1, 0]


# ---------- GET /ai/transactions/{id}/risk ----------

def test_stored_risk_endpoint(client, make_user, make_account, auth_headers):
    c, other, staff = make_user(), make_user(), make_user(role=UserRole.STAFF)
    txn = withdraw(client, auth_headers(c), make_account(c).id).json()
    r = client.get(f"/ai/transactions/{txn['id']}/risk", headers=auth_headers(c))
    assert r.status_code == 200
    assert r.json()["risk_score"] == txn["risk"]["risk_score"] and r.json()["is_model_generated"] is True
    assert client.get(f"/ai/transactions/{txn['id']}/risk", headers=auth_headers(staff)).status_code == 200
    assert client.get(f"/ai/transactions/{txn['id']}/risk", headers=auth_headers(other)).status_code == 404
    assert client.get("/ai/transactions/9999/risk", headers=auth_headers(c)).status_code == 404
    assert client.get(f"/ai/transactions/{txn['id']}/risk").status_code == 401


# ---------- GET /ai/model/info ----------

def test_model_info_staff_only(client, make_user, auth_headers):
    staff = make_user(role=UserRole.STAFF)
    r = client.get("/ai/model/info", headers=auth_headers(staff))
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == "rules-0.1" and body["model_kind"] == "rule-based"
    assert body["thresholds"] == {"low_max": 0.4, "medium_max": 0.7}
    assert "amount_ratio" in body["feature_names"]
    assert client.get("/ai/model/info", headers=auth_headers(make_user())).status_code == 403
    assert client.get("/ai/model/info").status_code == 401


# ---------- GET /ai/customers/{id}/insights ----------

def test_insights_access_rules(client, make_user, auth_headers):
    a, b, staff = make_user(), make_user(), make_user(role=UserRole.STAFF)
    url = f"/ai/customers/{a.profile.id}/insights"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth_headers(a)).status_code == 200
    assert client.get(url, headers=auth_headers(staff)).status_code == 200
    assert client.get(url, headers=auth_headers(b)).status_code == 404
    assert client.get("/ai/customers/9999/insights", headers=auth_headers(staff)).status_code == 404


def test_insights_are_labelled_as_model_generated(client, make_user, auth_headers):
    a = make_user()
    body = client.get(f"/ai/customers/{a.profile.id}/insights", headers=auth_headers(a)).json()
    assert body["is_model_generated"] is True
    assert body["generated_by"].startswith("rules-insights")
    assert "not part of the official account records" in body["disclaimer"]
    assert body["customer_id"] == a.profile.id and body["generated_at"]
    assert body["insights"] == [d["message"] for d in body["details"]]
    assert body["details"][0]["code"] == "NO_ACTIVITY"


def test_insights_detect_high_frequency_and_unusual_amount(client, db, make_user, make_account, auth_headers):
    a = make_user()
    acct = make_account(a, "1000.00")
    for i in range(6):
        db.add(Transaction(account_id=acct.id, transaction_type="DEBIT", amount=Decimal("10"), currency="GHS", reference=f"F-{i}", status="COMPLETED"))
    db.add(Transaction(account_id=acct.id, transaction_type="DEBIT", amount=Decimal("900"), currency="GHS", reference="F-big", status="COMPLETED"))
    db.commit()
    codes = {d["code"] for d in client.get(f"/ai/customers/{a.profile.id}/insights", headers=auth_headers(a)).json()["details"]}
    assert {"HIGH_FREQUENCY", "UNUSUAL_PATTERN", "SPENDING_EXCEEDS_INCOME"} <= codes


def test_insights_report_high_risk_and_flagged(client, db, make_user, make_account, auth_headers, monkeypatch):
    monkeypatch.setattr(risk_service, "_model", FixedModel(0.95))
    a = make_user()
    withdraw(client, auth_headers(a), make_account(a, "500.00").id, "20.00")
    codes = {d["code"] for d in client.get(f"/ai/customers/{a.profile.id}/insights", headers=auth_headers(a)).json()["details"]}
    assert {"HIGH_RISK_ACTIVITY", "FLAGGED_PENDING_REVIEW"} <= codes


def test_insights_never_change_banking_records(client, db, make_user, make_account, auth_headers):
    a = make_user()
    acct = make_account(a, "123.45")
    before = (db.query(Transaction).count(), db.query(RiskAssessment).count())
    client.get(f"/ai/customers/{a.profile.id}/insights", headers=auth_headers(a))
    db.refresh(acct)
    assert acct.balance == Decimal("123.45")
    assert (db.query(Transaction).count(), db.query(RiskAssessment).count()) == before


def test_insights_only_cover_that_customers_data(client, db, make_user, make_account, auth_headers):
    a, b = make_user(), make_user()
    acct_b = make_account(b, "1000.00")
    for i in range(6):
        db.add(Transaction(account_id=acct_b.id, transaction_type="DEBIT", amount=Decimal("10"), currency="GHS", reference=f"B-{i}", status="COMPLETED"))
    db.commit()
    codes = {d["code"] for d in client.get(f"/ai/customers/{a.profile.id}/insights", headers=auth_headers(a)).json()["details"]}
    assert codes == {"NO_ACTIVITY"}
