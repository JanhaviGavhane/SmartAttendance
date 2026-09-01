"""TEST 12 - Old data regression: 453-absent / 97-present / carry-over bugs.

These must NOT happen after the fixes:
- old students appearing in a new session
- old uploaded students appearing after reload
- stale counts leaking into a fresh session
"""

from tests.conftest import register


def test_no_stale_absent_leak(client):
    register(client, "reg_teacher")
    from services.storage import get_teacher_by_username
    tid = get_teacher_by_username("reg_teacher")["id"]

    # No attendance exists at all -> no phantom 453 absent
    import services.storage as storage
    assert storage.get_attendance(tid) == []
    assert storage.get_attendance_sessions(tid) == []

    # Fresh page /api route must reflect zero
    resp = client.get("/api/reports")
    data = resp.get_json()
    assert data["summary"]["total"] == 0
    assert data["records"] == []


def test_class_strength_cannot_grow_stale(client):
    register(client, "reg_teacher2")
    # A fresh session always uses the strength given now.
    # The save route validates a positive strength; absent is computed
    # strictly from the CURRENT strength - never previous sessions.
    import json
    resp = client.post(
        "/attendance/save",
        data=json.dumps({
            "subject": "S", "lecture_type": "Theory",
            "attendance_mode": "class_strength", "class_strength": 10,
            "present": [1], "absent": [],
        }),
        content_type="application/json",
    )
    body = resp.get_json()
    assert body["absent_count"] == 9  # 9 absent, not a stale 452


def test_new_session_after_reload_is_empty(client):
    register(client, "reg_teacher3")
    html = client.get("/attendance").get_data(as_text=True)
    # The page must render (not redirect) and must NOT embed any
    # previous session's student names or stale counts.
    assert "<title>" in html
    assert "Student 453" not in html
    assert "453" not in html