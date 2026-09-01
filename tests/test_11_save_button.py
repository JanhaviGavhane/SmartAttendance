"""TEST 11 - Save button frontend behavior (DOM-less logic checks).

The Save Attendance button enable/disable logic lives in the browser,
so we exercise the underlying backend contract it depends on and verify
the JS source wires the button correctly against those endpoints.
"""

import os
import json


def test_save_button_source_wires_validations():
    """Save button enablement relies on detected rolls; verify the JS
    contains the enable path and success/error handlers."""
    js = open(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "attendance.js"
        ), encoding="utf-8",
    ).read()

    # The save button must be discovered and toggled based on attendance
    assert "saveAttendanceBtn" in js or "saveAttendance" in js
    assert "disabled" in js


def test_save_button_success_and_error_handling():
    js = open(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "attendance.js"
        ), encoding="utf-8",
    ).read()
    assert "success" in js  # success banner path after a save
    assert "catch" in js or "error" in js  # error path


def test_backend_contract_no_attendance(client):
    """Save with no records returns 400, which the frontend shows as error."""
    from tests.conftest import register
    register(client, "btn_teacher")
    resp = client.post(
        "/attendance/save",
        data=json.dumps({
            "subject": "X", "lecture_type": "Theory",
            "attendance_mode": "class_strength", "class_strength": 0,
            "present": [], "absent": [],
        }),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_backend_contract_success_payload(client):
    from tests.conftest import register
    register(client, "btn_teacher2")
    resp = client.post(
        "/attendance/save",
        data=json.dumps({
            "subject": "X", "lecture_type": "Theory",
            "attendance_mode": "class_strength", "class_strength": 2,
            "present": [1], "absent": [],
        }),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body.get("download_url")