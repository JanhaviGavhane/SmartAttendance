"""TEST 14 - Fresh installation: auto DB init, register, login, upload,
take attendance, save; zero old data visible."""

import io
import json

from tests.conftest import register


def _csv(name, rows):
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Roll", "Name"])
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def test_fresh_install_workflow(client):
    # The isolated fixture already gives a brand-new empty DB.
    from services.storage import get_students, get_attendance
    assert get_students() == []

    # Register a teacher on the fresh DB
    resp = register(client, "new_teacher")
    assert resp.status_code == 200

    # Zero old students / attendance for this teacher on a fresh install
    assert client.get("/api/students").get_json()["students"] == []
    assert client.get("/api/reports").get_json()["records"] == []

    # Upload new students
    content = _csv("fresh.csv", [[1, "Fresh One"], [2, "Fresh Two"]])
    resp = client.post(
        "/students/upload",
        data={"file": (io.BytesIO(content), "fresh.csv")},
        content_type="multipart/form-data",
    )
    assert resp.get_json()["success"] is True

    # New session upload for attendance
    resp = client.post(
        "/session/students",
        data={"file": (io.BytesIO(content), "fresh.csv")},
        content_type="multipart/form-data",
    )
    assert resp.get_json()["success"] is True

    # Take + save attendance
    payload = {
        "subject": "Computer Science",
        "lecture_type": "Theory",
        "attendance_mode": "file_upload",
        "present": [1],
        "absent": [],
        "students": [{"roll": 1, "name": "Fresh One"},
                     {"roll": 2, "name": "Fresh Two"}],
        "date": "2026-09-01",
        "time": "09:00 AM",
    }
    resp = client.post(
        "/attendance/save",
        data=json.dumps(payload),
        content_type="application/json",
    )
    body = resp.get_json()
    assert body["success"] is True
    assert body["present_count"] == 1
    assert body["absent_count"] == 1

    # Only the new teacher's data appears
    data = client.get("/api/reports").get_json()
    assert len(data["records"]) == 2


def test_no_hardcoded_account(client):
    from tests.conftest import login
    # Old janhavi/1234 must NOT be the only account
    resp = login(client, "janhavi", "1234")
    text = resp.get_data(as_text=True)
    assert "Invalid" in text or "error" in text.lower()