"""TEST 1 - Application startup: imports, routes, DB auto-init."""

import pytest


def test_app_imports():
    import app as appmod
    assert appmod.app is not None


def test_routes_exist(client):
    import app as appmod
    rules = list(appmod.app.url_map.iter_rules())
    paths = {r.rule for r in rules}
    expected = {
        "/",
        "/login",
        "/register",
        "/logout",
        "/dashboard",
        "/attendance",
        "/students",
        "/students/upload",
        "/session/students",
        "/attendance/save",
        "/api/students",
        "/api/reports",
        "/reports/csv",
        "/reports/attendance-csv",
        "/calendar",
        "/api/calendar",
        "/settings",
        "/syllabus",
        "/api/syllabus",
        "/transcribe",
    }
    missing = expected - paths
    assert not missing, f"Missing routes: {missing}"


def test_all_tables_auto_created(_isolated_storage):
    import services.storage as storage
    storage.ensure_data_folder()
    conn = storage._get_connection()
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    required = {
        "students",
        "attendance_sessions",
        "attendance_records",
        "teachers",
        "syllabus_subjects",
        "syllabus_units",
        "syllabus_topics",
    }
    assert required.issubset(tables), f"Missing tables: {required - tables}"


def test_no_proxy_tables_or_columns(_isolated_storage):
    import services.storage as storage
    storage.ensure_data_folder()
    conn = storage._get_connection()
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "voice_profiles" not in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(attendance_records)")}
    assert "proxy_status" not in cols
    assert "proxy_confidence" not in cols