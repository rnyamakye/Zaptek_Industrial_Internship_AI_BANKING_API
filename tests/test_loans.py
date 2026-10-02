def test_create_loan(client, make_user, auth_headers):
    user = make_user()

    response = client.post(
        "/loans",
        json={
            "amount": 5000,
            "interest_rate": 10,
            "duration": 12,
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["amount"] == "5000.00"
    assert data["interest_rate"] == "10.00"
    assert data["duration"] == 12
    assert data["status"] == "PENDING"


def test_list_loans(client, make_user, auth_headers):
    user = make_user()

    client.post(
        "/loans",
        json={
            "amount": 5000,
            "interest_rate": 10,
            "duration": 12,
        },
        headers=auth_headers(user),
    )

    response = client.get(
        "/loans",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["duration"] == 12
    assert response.headers["X-Total-Count"] == "1"


def test_get_single_loan(client, make_user, auth_headers):
    user = make_user()

    create_response = client.post(
        "/loans",
        json={
            "amount": 5000,
            "interest_rate": 10,
            "duration": 12,
        },
        headers=auth_headers(user),
    )

    loan_id = create_response.json()["id"]

    response = client.get(
        f"/loans/{loan_id}",
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json()["id"] == loan_id


def test_unauthorized_loan_request(client):
    response = client.get("/loans")

    assert response.status_code == 401


def test_loan_not_found(client, make_user, auth_headers):
    user = make_user()

    response = client.get(
        "/loans/99999",
        headers=auth_headers(user),
    )

    assert response.status_code == 404
    