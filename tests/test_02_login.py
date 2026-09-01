"""TEST 2 - Login: valid/invalid, logout, protected pages."""


def test_login_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_register_then_dashboard(client):
    from tests.conftest import register
    resp = register(client, "alice")
    assert "dashboard" in resp.request.path or resp.status_code == 200


def test_invalid_login_rejected(client, _isolated_storage):
    from tests.conftest import register, login
    register(client, "alice")
    client.get("/logout")
    resp = login(client, "alice", "wrongpassword")
    data = resp.get_data(as_text=True)
    assert "Invalid" in data or "error" in data.lower()


def test_valid_login_redirects(client):
    from tests.conftest import register, login
    register(client, "bob")
    client.get("/logout")
    resp = login(client, "bob")
    assert resp.status_code == 200


def test_logout(client):
    from tests.conftest import register, login
    register(client, "charlie")
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    # Must now be redirected to login on protected page
    assert client.get("/dashboard").status_code == 302


def test_protected_page_requires_login(client):
    assert client.get("/dashboard").status_code == 302
    assert client.get("/attendance").status_code == 302
    assert client.get("/students").status_code == 302


def test_protected_api_requires_login(client):
    assert client.get("/api/students").status_code == 401
    assert client.get("/api/reports").status_code == 401