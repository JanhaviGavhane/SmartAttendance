"""TEST 16 - All pages return 200 when logged in; unauthorized redirects."""

from tests.conftest import register

PAGES = [
    "/dashboard",
    "/attendance",
    "/students",
    "/settings",
    "/syllabus",
    "/reports",
    "/calendar",
]


def test_pages_200_when_logged_in(client):
    register(client, "page_teacher")
    for page in PAGES:
        resp = client.get(page)
        assert resp.status_code == 200, f"{page} -> {resp.status_code}"


def test_unauthorized_redirect(client):
    for page in PAGES:
        resp = client.get(page, follow_redirects=False)
        assert resp.status_code == 302, f"{page} unauthenticated -> {resp.status_code}"


def test_login_page_accessible_unauthenticated(client):
    assert client.get("/").status_code == 200
    assert client.get("/register").status_code == 200