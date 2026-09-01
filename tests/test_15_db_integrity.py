"""TEST 15 - Database integrity: tables, FKs, teacher_id association."""

import sqlite3


def test_required_tables_and_fks(_isolated_storage):
    import services.storage as storage
    storage.ensure_data_folder()
    conn = storage._get_connection()

    tables = {
        r[0]: None
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for t in (
        "teachers",
        "students",
        "attendance_sessions",
        "attendance_records",
        "syllabus_topics",
    ):
        assert t in tables

    # Teacher columns present
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(teachers)")}
    assert {"id", "username", "password_hash"}.issubset(tcols)

    # teacher_id present on data tables
    scol = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    assert "teacher_id" in scol
    acol = {r[1] for r in conn.execute("PRAGMA table_info(attendance_records)")}
    assert "teacher_id" in acol
    sess = {r[1] for r in conn.execute("PRAGMA table_info(attendance_sessions)")}
    assert "teacher_id" in sess


def test_teacher_id_correctly_associated(client):
    from tests.conftest import register
    register(client, "db_teacher")
    from services.storage import get_teacher_by_username
    tid = get_teacher_by_username("db_teacher")["id"]

    import services.storage as storage
    storage.replace_students(
        [{"roll": 1, "name": "Db One"}], teacher_id=tid
    )
    conn = storage._get_connection()
    rows = conn.execute(
        "SELECT teacher_id FROM students WHERE roll = 1"
    ).fetchall()
    assert rows and rows[0]["teacher_id"] == tid


def test_session_and_records_linked_by_teacher(client):
    """Attendance sessions from different teachers don't collide on the
    (date,time,subject,lecture_type) UNIQUE constraint."""
    import json
    from tests.conftest import register

    # Teacher 1 saves
    register(client, "t1")
    resp = client.post(
        "/attendance/save",
        data=json.dumps({
            "subject": "SameSubject", "lecture_type": "Theory",
            "attendance_mode": "class_strength", "class_strength": 2,
            "present": [1], "absent": [],
            "date": "2026-09-02", "time": "10:00 AM",
        }),
        content_type="application/json",
    )
    assert resp.get_json()["success"] is True

    # Teacher 2 saves with identical date/time/subject/lecture_type
    client.get("/logout")
    register(client, "t2")
    resp = client.post(
        "/attendance/save",
        data=json.dumps({
            "subject": "SameSubject", "lecture_type": "Theory",
            "attendance_mode": "class_strength", "class_strength": 2,
            "present": [2], "absent": [],
            "date": "2026-09-02", "time": "10:00 AM",
        }),
        content_type="application/json",
    )
    assert resp.get_json()["success"] is True

    import services.storage as storage
    from services.storage import get_teacher_by_username
    tid1 = get_teacher_by_username("t1")["id"]
    tid2 = get_teacher_by_username("t2")["id"]
    s1 = storage.get_attendance_sessions(tid1)
    s2 = storage.get_attendance_sessions(tid2)
    assert len(s1) == 1 and len(s2) == 1  # no cross-collision