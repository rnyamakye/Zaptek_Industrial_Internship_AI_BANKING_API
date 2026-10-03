from datetime import date

from app.models import Notification
from app.models.enums import NotificationType, UserRole


def request_card(client, user, auth_headers, card_type="DEBIT"):
    return client.post("/cards", json={"card_type": card_type}, headers=auth_headers(user))


# ---------- cards ----------

def test_cards_require_login(client):
    assert client.get("/cards").status_code == 401
    assert client.post("/cards", json={"card_type": "DEBIT"}).status_code == 401


def test_customer_requests_card_only_last_four_digits_exposed(client, make_user, auth_headers):
    c = make_user()
    r = request_card(client, c, auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "customer_id", "card_type", "last_four_digits", "expiry_date", "status"}
    assert len(body["last_four_digits"]) == 4 and body["last_four_digits"].isdigit()
    assert body["status"] == "ACTIVE"
    assert date.fromisoformat(body["expiry_date"]) > date.today()


def test_invalid_card_type_is_422(client, make_user, auth_headers):
    assert request_card(client, make_user(), auth_headers, "GOLD").status_code == 422


def test_customer_sees_only_own_cards(client, make_user, auth_headers):
    a, b = make_user(), make_user()
    request_card(client, a, auth_headers)
    assert client.get("/cards", headers=auth_headers(b)).json() == []
    assert len(client.get("/cards", headers=auth_headers(a)).json()) == 1


def test_customer_can_block_but_not_unblock(client, make_user, auth_headers):
    c, staff = make_user(), make_user(role=UserRole.STAFF)
    cid = request_card(client, c, auth_headers).json()["id"]
    assert client.patch(f"/cards/{cid}", json={"status": "BLOCKED"}, headers=auth_headers(c)).json()["status"] == "BLOCKED"
    assert client.patch(f"/cards/{cid}", json={"status": "ACTIVE"}, headers=auth_headers(c)).status_code == 403
    assert client.patch(f"/cards/{cid}", json={"status": "ACTIVE"}, headers=auth_headers(staff)).json()["status"] == "ACTIVE"


def test_customer_cannot_touch_another_customers_card(client, make_user, auth_headers):
    a, b = make_user(), make_user()
    cid = request_card(client, a, auth_headers).json()["id"]
    assert client.patch(f"/cards/{cid}", json={"status": "BLOCKED"}, headers=auth_headers(b)).status_code == 404


# ---------- notifications ----------

def seed(db, user, n=3):
    for i in range(n):
        db.add(Notification(user_id=user.id, type=NotificationType.SYSTEM, title=f"N{i}", message="m"))
    db.commit()


def test_notifications_require_login(client):
    assert client.get("/notifications").status_code == 401


def test_user_sees_only_own_notifications_newest_first(client, db, make_user, auth_headers):
    a, b = make_user(), make_user()
    seed(db, a, 3)
    seed(db, b, 2)
    r = client.get("/notifications", headers=auth_headers(a))
    assert [n["title"] for n in r.json()] == ["N2", "N1", "N0"]
    assert r.headers["X-Total-Count"] == "3"


def test_mark_read_and_unread_filter(client, db, make_user, auth_headers):
    a = make_user()
    seed(db, a, 2)
    first = client.get("/notifications", headers=auth_headers(a)).json()[0]
    r = client.patch(f"/notifications/{first['id']}/read", headers=auth_headers(a))
    assert r.status_code == 200 and r.json()["read"] is True
    assert len(client.get("/notifications?unread=true", headers=auth_headers(a)).json()) == 1


def test_cannot_mark_someone_elses_notification(client, db, make_user, auth_headers):
    a, b = make_user(), make_user()
    seed(db, a, 1)
    nid = client.get("/notifications", headers=auth_headers(a)).json()[0]["id"]
    assert client.patch(f"/notifications/{nid}/read", headers=auth_headers(b)).status_code == 404
    assert client.patch("/notifications/9999/read", headers=auth_headers(a)).status_code == 404
