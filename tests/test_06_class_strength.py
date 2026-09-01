"""TEST 6 - Class strength: present/absent math + fresh str each session."""

import json

from tests.conftest import register


def _auth(client):
    register(client, "strength_teacher")


def _save(client, present, strength):
    payload = {
        "subject": "Maths",
        "lecture_type": "Theory",
        "attendance_mode": "class_strength",
        "class_strength": strength,
        "present": present,
        "absent": [],
        "date": "2026-06-01",
        "time": "10:00 AM",
    }
    return client.post(
        "/attendance/save",
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_strength_10_present_3(client):
    _auth(client)
    resp = _save(client, present=[1, 2, 3], strength=10)
    body = resp.get_json()
    assert body["success"] is True
    assert body["present_count"] == 3
    assert body["absent_count"] == 7


def test_strength_20_present_5(client):
    _auth(client)
    resp = _save(client, present=[1, 2, 3, 4, 5], strength=20)
    body = resp.get_json()
    assert body["present_count"] == 5
    assert body["absent_count"] == 15


def test_strength_100_present_3(client):
    _auth(client)
    resp = _save(client, present=[1, 2, 3], strength=100)
    body = resp.get_json()
    assert body["present_count"] == 3
    assert body["absent_count"] == 97


def test_strength_not_retained_between_sessions(client):
    _auth(client)
    _save(client, present=[1, 2, 3], strength=10)
    # New session: strength must be whatever is supplied now (20), not 10
    resp = _save(client, present=[1, 2, 3], strength=20)
    body = resp.get_json()
    assert body["class_strength"] == 20
    assert body["absent_count"] == 17


def test_no_present_is_zero(client):
    _auth(client)
    resp = _save(client, present=[], strength=10)
    body = resp.get_json()
    assert body["present_count"] == 0
    assert body["absent_count"] == 10