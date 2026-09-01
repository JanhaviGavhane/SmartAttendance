"""Shared pytest fixtures: isolated temp DB + app test client.

Every test runs against a throwaway SQLite database under the OS temp
directory so the real development database (data/smart_attendance.db)
is never touched.
"""

import os
import sys
import shutil
import tempfile

import pytest


@pytest.fixture(scope="function", autouse=True)
def _isolated_storage():
    """Point the storage module at a throwaway directory + DB.

    Function-scoped so every test starts from a brand-new empty database
    (no cross-test contamination from shared table state or usernames).
    """
    import services.storage as storage

    tmpdir = tempfile.mkdtemp(prefix="smart_attendance_tests_")

    original = {
        key: getattr(storage, key)
        for key in (
            "DATA_DIR",
            "STUDENTS_FILE",
            "ATTENDANCE_FILE",
            "SYLLABUS_FILE",
            "DB_FILE",
            "UPLOADS_DIR",
            "_connection",
        )
    }

    storage.DATA_DIR = tmpdir
    storage.STUDENTS_FILE = os.path.join(tmpdir, "students.csv")
    storage.ATTENDANCE_FILE = os.path.join(tmpdir, "attendance.csv")
    storage.SYLLABUS_FILE = os.path.join(tmpdir, "syllabus.json")
    storage.DB_FILE = os.path.join(tmpdir, "smart_attendance.db")
    storage.UPLOADS_DIR = os.path.join(tmpdir, "uploads")
    storage._connection = None

    yield

    conn = storage._connection
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    storage._connection = None
    for key, value in original.items():
        setattr(storage, key, value)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture()
def client(_isolated_storage):
    """Return an app test client with a fresh isolated DB."""
    import app as appmod
    appmod.app.config["TESTING"] = True
    return appmod.app.test_client()


def register(client, username, password="pass1234"):
    """Register a new teacher and return the session-scoped client."""
    resp = client.post(
        "/register",
        data={
            "username": username,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )
    return resp


def login(client, username, password="pass1234"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def db_conn():
    """Return the shared storage connection WITHOUT closing it.

    The storage module caches one connection for the whole process;
    tests must never close it (that would poison later tests).
    """
    import services.storage as storage
    return storage._get_connection()