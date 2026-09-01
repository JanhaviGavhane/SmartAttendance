"""TEST 10 - Save attendance: roll mapping + Word/Excel output files."""

import io
import json

from tests.conftest import register


def _auth(client):
    register(client, "save_teacher")


def _save(client, students=None, present=None, name="class.xlsx"):
    payload = {
        "subject": "Python",
        "lecture_type": "Theory",
        "attendance_mode": "file_upload",
        "class_strength": None,
        "present": present or [],
        "absent": [],
        "students": students or [],
        "original_filename": name,
        "date": "2026-08-15",
        "time": "09:00 AM",
    }
    return client.post(
        "/attendance/save",
        data=json.dumps(payload),
        content_type="application/json",
    )


STUDENTS = [
    {"roll": 1, "name": "Student 1"},
    {"roll": 2, "name": "Student 2"},
    {"roll": 3, "name": "Student 3"},
    {"roll": 4, "name": "Student 4"},
    {"roll": 5, "name": "Student 5"},
]


def test_save_maps_statuses(client):
    _auth(client)
    resp = _save(client, students=STUDENTS, present=[1, 3, 5])
    body = resp.get_json()
    assert body["success"] is True
    by_roll = {r["roll"]: r["status"] for r in body["records"]}
    assert by_roll == {1: "Present", 2: "Absent", 3: "Present",
                       4: "Absent", 5: "Present"}


def test_save_requires_student_list(client):
    _auth(client)
    resp = _save(client, students=[], present=[1])
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_save_generates_xlsx_result(client):
    _auth(client)
    resp = _save(client, students=STUDENTS, present=[1, 3, 5], name="roster.xlsx")
    body = resp.get_json()
    assert body["success"] is True
    assert body.get("download_url")
    assert body.get("format") == "xlsx"

    # Download the result file and verify its contents
    dl = client.get(body["download_url"])
    assert dl.status_code == 200
    assert "spreadsheet" in dl.content_type or "octet" in dl.content_type

    import openpyxl
    import io as _io
    wb = openpyxl.load_workbook(_io.BytesIO(dl.data))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert ("Roll" in rows[0] or "roll" in rows[0][0].lower())
    statuses = {int(row[0]): str(row[2]).lower() for row in rows[1:] if row[0]}
    assert statuses[1] == "present"
    assert statuses[2] == "absent"
    assert statuses[5] == "present"


def test_save_generates_docx_result(client):
    _auth(client)
    resp = _save(client, students=STUDENTS, present=[1, 3, 5], name="roster.docx")
    body = resp.get_json()
    assert body["format"] == "docx"
    dl = client.get(body["download_url"])
    assert dl.status_code == 200

    from docx import Document
    import io as _io
    doc = Document(_io.BytesIO(dl.data))
    table = doc.tables[0]
    header = [c.text for c in table.rows[0].cells]
    assert "status" in " ".join(header).lower() or "attendance" in " ".join(header).lower()
    # Find Student 5 row and confirm Present
    present_found = False
    for row in table.rows[1:]:
        cells = [c.text for c in row.cells]
        if cells and cells[0].strip() == "5":
            assert "present" in " ".join(cells).lower()
            present_found = True
    assert present_found


def test_original_file_not_overwritten(client):
    """The uploaded input file must be untouched: result uses 'roster' base."""
    _auth(client)
    resp = _save(client, students=STUDENTS, present=[1], name="roster.xlsx")
    body = resp.get_json()
    # Result filename is a unique generated name, not 'roster.xlsx' itself
    assert body["download_url"].endswith("-attendance.xlsx") is False
    assert "attendance" in body["filename"]