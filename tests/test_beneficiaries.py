from app.models.enums import BeneficiaryStatus


def test_create_beneficiary(client, make_user, auth_headers):
    user = make_user()

    response = client.post(
        "/beneficiaries",
        json={
            "name": "John Doe",
            "account_number": "1234567890",
            "bank_name": "Test Bank",
        },
        headers=auth_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "John Doe"
    assert data["account_number"] == "1234567890"
    assert data["bank_name"] == "Test Bank"
    assert data["status"] == BeneficiaryStatus.ACTIVE.value


def test_list_beneficiaries(client, make_user, auth_headers):
    user = make_user()

    client.post(
        "/beneficiaries",
        json={
            "name": "John Doe",
            "account_number": "1234567890",
            "bank_name": "Test Bank",
        },
        headers=auth_headers(user),
    )

    response = client.get(
        "/beneficiaries",
        headers=auth_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "John Doe"
    assert response.headers["X-Total-Count"] == "1"


def test_delete_beneficiary(client, make_user, auth_headers):
    user = make_user()

    create_response = client.post(
        "/beneficiaries",
        json={
            "name": "John Doe",
            "account_number": "1234567890",
            "bank_name": "Test Bank",
        },
        headers=auth_headers(user),
    )

    beneficiary_id = create_response.json()["id"]

    response = client.delete(
        f"/beneficiaries/{beneficiary_id}",
        headers=auth_headers(user),
    )

    assert response.status_code == 204

    list_response = client.get(
        "/beneficiaries",
        headers=auth_headers(user),
    )

    assert list_response.status_code == 200

    data = list_response.json()

    assert data[0]["status"] == BeneficiaryStatus.INACTIVE.value


def test_unauthorized_beneficiary_request(client):
    response = client.get("/beneficiaries")

    assert response.status_code == 401


def test_duplicate_beneficiary(client, make_user, auth_headers):
    user = make_user()

    beneficiary = {
        "name": "John Doe",
        "account_number": "1234567890",
        "bank_name": "Test Bank",
    }

    first_response = client.post(
        "/beneficiaries",
        json=beneficiary,
        headers=auth_headers(user),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/beneficiaries",
        json=beneficiary,
        headers=auth_headers(user),
    )

    assert second_response.status_code == 409