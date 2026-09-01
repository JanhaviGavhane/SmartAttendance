"""TEST 7 - Duplicates: repeated rolls never counted twice."""

import json

from tests.conftest import register


def _auth(client):
    register(client, "dupe_teacher")


def _save(client, present):
    payload = {
        "subject": "Physics",
        "lecture_type": "Theory",
        "attendance_mode": "class_strength",
        "class_strength": 5,
        "present": present,
        "absent": [],
        "date": "2026-07-01",
        "time": "10:00 AM",
    }
    return client.post(
        "/attendance/save",
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_duplicate_present_not_duplicated(client):
    _auth(client)
    resp = _save(client, present=[1, 1, 1, 5, 5])
    body = resp.get_json()
    assert body["present_count"] == 2
    present_rolls = {r["roll"] for r in body["records"] if r["status"] == "Present"}
    assert present_rolls == {1, 5}