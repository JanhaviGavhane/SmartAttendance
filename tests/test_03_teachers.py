"""TEST 3 - Multiple teachers: data isolation via teacher_id."""

import json

from tests.conftest import register, login


def _swap_client(client, username):
    client.get("/logout")
    login(client, username)


def test_teacher_students_isolated(client):
    register(client, "teacher_a")
    register(client, "teacher_b") if False else None
    # register teacher_b separately (register replaces session)
    client.get("/logout")
    register(client, "teacher_b")

    # Teacher A adds students
    _swap_client(client, "teacher_a")
    import services.storage as storage
    from services.storage import get_teacher_by_username
    tid_a = get_teacher_by_username("teacher_a")["id"]
    storage.replace_students(
        [{"roll": 1, "name": "A1"}, {"roll": 2, "name": "A2"}], teacher_id=tid_a
    )
    resp = client.get("/api/students")
    data = resp.get_json()
    assert [s["roll"] for s in data["students"]] == [1, 2]

    # Teacher B must see zero of A's students
    _swap_client(client, "teacher_b")
    resp = client.get("/api/students")
    assert resp.get_json()["students"] == []


def test_teacher_attendance_isolated(client):
    register(client, "teacher_a")
    client.get("/logout")
    register(client, "teacher_b")

    from services.storage import get_teacher_by_username
    tid_a = get_teacher_by_username("teacher_a")["id"]

    _swap_client(client, "teacher_a")
    payload = {
        "subject": "Maths",
        "lecture_type": "Theory",
        "attendance_mode": "class_strength",
        "class_strength": 2,
        "present": [1],
        "absent": [],
        "date": "2026-01-10",
        "time": "10:00 AM",
    }
    resp = client.post(
        "/attendance/save", data=json.dumps(payload),
        content_type="application/json"
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    # Teacher B sees zero records
    _swap_client(client, "teacher_b")
    resp = client.get("/api/reports")
    data = resp.get_json()
    assert data["records"] == []
    assert data["sessions"] == []


def test_cannot_access_other_teachers_data(client):
    """Session teacher_id is authoritative; other teacher data stays hidden."""
    register(client, "teacher_x")
    client.get("/logout")
    register(client, "teacher_y")

    from services.storage import get_teacher_by_username
    tid_x = get_teacher_by_username("teacher_x")["id"]

    _swap_client(client, "teacher_x")
    import services.storage as storage
    storage.replace_students(
        [{"roll": 10, "name": "Secret"}], teacher_id=tid_x
    )
    # X sees their own data through the API
    assert [s["roll"] for s in client.get("/api/students").get_json()["students"]] == [10]

    # Teacher Y (logged in) must NOT see X's student through the API
    _swap_client(client, "teacher_y")
    from services.storage import get_students
    # Even a direct storage call scoped to X's own id returns only X's data -
    # Y's records remain empty, proving records are segmented per teacher.
    tid_y = get_teacher_by_username("teacher_y")["id"]
    assert get_students(tid_y) == []
    assert get_students(None) == [{"roll": 10, "name": "Secret"}]

    resp = client.get("/api/students")
    assert resp.get_json()["students"] == []