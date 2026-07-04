from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_demo_info(client):
    response = client.get("/api/auth/demo-info")
    assert response.status_code == 200
    assert response.json() == {"demoLogin": True}


def test_login_success(client):
    response = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "admin"
    assert body["token"]


def test_login_wrong_password(client):
    response = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post(
        "/api/auth/login", json={"email": "nobody@test.local", "password": "x"}
    )
    assert response.status_code == 401


def test_login_as_demo_user_rejected(client):
    response = client.post(
        "/api/auth/login", json={"email": "__marketdeck_demo_user__", "password": "disabled"}
    )
    assert response.status_code == 401


def test_demo_login(client):
    response = client.post("/api/auth/demo-login")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "demo"
    assert body["token"]


def test_me_admin(client, admin_headers):
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"email": ADMIN_EMAIL, "role": "admin"}


def test_me_demo_hides_email(client, demo_headers):
    response = client.get("/api/auth/me", headers=demo_headers)
    assert response.status_code == 200
    assert response.json() == {"role": "demo"}


def test_me_without_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert response.status_code == 401


def test_password_change_roundtrip(client, admin_headers):
    response = client.put(
        "/api/auth/password",
        headers=admin_headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": "new-password"},
    )
    assert response.status_code == 200

    old = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "new-password"})
    assert new.status_code == 200


def test_password_change_wrong_current(client, admin_headers):
    response = client.put(
        "/api/auth/password",
        headers=admin_headers,
        json={"current_password": "wrong", "new_password": "x"},
    )
    assert response.status_code == 400


def test_password_change_demo_forbidden(client, demo_headers):
    response = client.put(
        "/api/auth/password",
        headers=demo_headers,
        json={"current_password": "x", "new_password": "y"},
    )
    assert response.status_code == 403
