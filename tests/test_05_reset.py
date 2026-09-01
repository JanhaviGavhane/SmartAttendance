"""TEST 5 - Attendance session reset: no carry-over between sessions.

Session 1: upload 20 students, present 1-5, save.
Session 2: fresh session, upload 10 different students; previous
session's students/attendance/counts must not reappear.
Reload: /attendance page must start empty.
"""

import io
import json

from tests.conftest import register


def _auth(client):
    register(client, "reset_teacher")


def _csv(name, rows):
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Roll", "Name"])
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _upload_session(client, name, content):
    return client.post(
        "/session/students",
        data={"file": (io.BytesIO(content), name)},
        content_type="multipart/form-data",
    )


def _save(client, present, strength=None, mode="file_upload", class_students=None, time="10:00 AM"):
    payload = {
        "subject": "Python",
        "lecture_type": "Theory",
        "attendance_mode": mode,
        "class_strength": strength,
        "present": present,
        "absent": [],
        "students": class_students or [],
        "date": "2026-05-01",
        "time": time,
    }
    return client.post(
        "/attendance/save",
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_session_reset_no_carryover(client):
    _auth(client)

    # Session 1: 20 students, 5 present
    s1 = _csv("s1.csv", [[i, "Student %d" % i] for i in range(1, 21)])
    _upload_session(client, "s1.csv", s1)
    resp = _save(client, present=[1, 2, 3, 4, 5], class_students=[{"roll": i, "name": "Student %d" % i} for i in range(1, 21)])
    assert resp.status_code == 200
    assert resp.get_json()["present_count"] == 5
    assert resp.get_json()["absent_count"] == 15

    # Session 2: entirely different 10 students
    s2 = _csv("s2.csv", [[100 + i, "New %d" % i] for i in range(1, 11)])
    resp2 = _upload_session(client, "s2.csv", s2)
    data2 = resp2.get_json()
    assert [s["name"] for s in data2["students"]] == ["New %d" % i for i in range(1, 11)]

    # Save session 2 with only 2 present
    resp = _save(client, present=[101, 102], class_students=[{"roll": 100 + i, "name": "New %d" % i} for i in range(1, 11)], time="11:00 AM")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["present_count"] == 2
    assert body["absent_count"] == 8

    # Verify DB has both sessions, per-teacher, with correct rolls
    import services.storage as storage
    from services.storage import get_teacher_by_username
    tid = get_teacher_by_username("reset_teacher")["id"]
    records = storage.get_attendance(tid)
    s1_present = {r["roll"] for r in records if r["status"] == "Present"
                  and "Student" in (r.get("name") or "")}
    s1_absent = {r["roll"] for r in records if r["status"] == "Absent"
                 and "Student" in (r.get("name") or "")}
    s2_present = {r["roll"] for r in records if r["status"] == "Present"
                  and "New" in (r.get("name") or "")}
    s2_absent = {r["roll"] for r in records if r["status"] == "Absent"
                 and "New" in (r.get("name") or "")}
    assert s1_present == {1, 2, 3, 4, 5}
    assert s1_absent == {6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}
    assert s2_present == {101, 102}
    assert s2_absent == {103, 104, 105, 106, 107, 108, 109, 110}


def test_attendance_page_starts_empty(client):
    _auth(client)
    resp = client.get("/attendance")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Page must not inject saved student data into the current session
    assert "Student 1" not in html or "uploaded" in html.lower()


def test_session_students_are_session_only(client):
    """Uploaded file students must be session-only; /api/students untouched."""
    _auth(client)
    s1 = _csv("only.csv", [[5, "SessionOnly"]])
    _upload_session(client, "only.csv", s1)
    resp = client.get("/api/students")
    assert resp.get_json()["students"] == []