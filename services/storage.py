

# ===== DATA STORAGE SERVICE =====
#
# SQLite-backed persistent storage for the Smart Attendance app.
#
#   data/
#       smart_attendance.db   -> SQLite database (all tables below)
#       students.csv          -> kept as-is (legacy, read on migration)
#       attendance.csv        -> kept as-is (legacy, read on migration)
#       syllabus.json         -> kept as-is (legacy, read on migration)
#
# On first load the legacy CSV/JSON files are migrated into the database,
# after which the database is the single source of truth.
#
# Tables:
#
#   students
#       roll INTEGER PRIMARY KEY, name TEXT NOT NULL
#
#   attendance_sessions
#       id INTEGER PRIMARY KEY,
#       date TEXT, time TEXT, subject TEXT, lecture_type TEXT,
#       attendance_mode TEXT,          -- 'file_upload' | 'class_strength'
#       class_strength INTEGER,
#       UNIQUE(date, time, subject, lecture_type)
#
#   attendance_records
#       id INTEGER PRIMARY KEY,
#       session_id INTEGER,            -- FK -> attendance_sessions.id
#       date TEXT, time TEXT, roll INTEGER, name TEXT,
#       status TEXT, subject TEXT, lecture_type TEXT,
#       attendance_mode TEXT, class_strength INTEGER
#
#   syllabus_subjects
#       id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
#
#   syllabus_units
#       id INTEGER PRIMARY KEY, subject_id INTEGER, name TEXT NOT NULL
#
#   syllabus_topics
#       id INTEGER PRIMARY KEY, unit_id INTEGER, title TEXT NOT NULL,
#       completed INTEGER DEFAULT 0, completed_date TEXT, notes TEXT
#
# The data folder is created automatically if it does not exist.
# Data survives a Flask restart because it is stored in SQLite on disk.

import os
import sqlite3
import threading
import json

from datetime import date, datetime


# ============================================================
# ===== PATHS =================================================
# ============================================================

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(_BASE_DIR, "data")

STUDENTS_FILE = os.path.join(DATA_DIR, "students.csv")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.csv")
SYLLABUS_FILE = os.path.join(DATA_DIR, "syllabus.json")

DB_FILE = os.path.join(DATA_DIR, "smart_attendance.db")

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

# A single connection per worker is fine for this single-process app.
# sqlite3 connections are used under a lock so concurrent requests are safe.
_connection = None
_lock = threading.Lock()


# ============================================================
# ===== DB HELPERS ============================================
# ============================================================

def _get_connection():
    """Return the shared SQLite connection, creating the schema if needed."""

    global _connection

    if _connection is not None:
        return _connection

    os.makedirs(DATA_DIR, exist_ok=True)

    _connection = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA foreign_keys = ON")

    _create_schema(_connection)

    return _connection


def _create_schema(conn):
    """Create all tables if they do not exist."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS teachers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            created_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS students (
            roll        INTEGER NOT NULL,
            name        TEXT NOT NULL,
            teacher_id  INTEGER,
            PRIMARY KEY (roll, teacher_id)
        );

        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT NOT NULL,
            time            TEXT NOT NULL,
            subject         TEXT NOT NULL,
            lecture_type    TEXT NOT NULL,
            attendance_mode TEXT,
            class_strength  INTEGER,
            teacher_id      INTEGER,
            session_uuid    TEXT
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id        INTEGER,
            date              TEXT NOT NULL,
            time              TEXT NOT NULL,
            roll              INTEGER,
            name              TEXT,
            status            TEXT NOT NULL,
            subject           TEXT NOT NULL,
            lecture_type      TEXT NOT NULL,
            attendance_mode   TEXT,
            class_strength    INTEGER,
            teacher_id        INTEGER
        );

        CREATE TABLE IF NOT EXISTS syllabus_subjects (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS syllabus_units (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id  INTEGER NOT NULL,
            name        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS syllabus_topics (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id          INTEGER NOT NULL,
            title            TEXT NOT NULL,
            completed        INTEGER DEFAULT 0,
            completed_date   TEXT,
            notes            TEXT DEFAULT ''
        );

        """
    )

    conn.commit()


def ensure_data_folder():
    """Ensure the data folder exists and migrate any legacy data."""

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    conn = _get_connection()

    with _lock:
        _migrate_add_teacher_id(conn)
        _migrate_add_session_uuid(conn)
        _migrate_legacy(conn)


# ============================================================
# ===== MIGRATION: ADD teacher_id COLUMN =====================
# ============================================================

def _migrate_add_teacher_id(conn):
    """Add the teacher_id column to tables created before multi-teacher
    support. Runs after schema creation to handle existing databases."""

    _add_column_if_missing(conn, "students", "teacher_id", "INTEGER")
    _add_column_if_missing(
        conn, "attendance_sessions", "teacher_id", "INTEGER"
    )
    _add_column_if_missing(
        conn, "attendance_records", "teacher_id", "INTEGER"
    )

    _rebuild_students_pk_if_needed(conn)


def _migrate_add_session_uuid(conn):
    """Add the session_uuid column to attendance_sessions for databases
    created before unique per-session identity was added.

    Legitimate attendance sessions are keyed by a client-generated
    session_uuid instead of (date, time, subject, lecture_type) so two
    genuine sessions with the same minute-precision timestamp can never
    overwrite each other. Legacy rows keep a NULL session_uuid and still
    load/report correctly.
    """

    _add_column_if_missing(
        conn, "attendance_sessions", "session_uuid", "TEXT"
    )


def _rebuild_students_pk_if_needed(conn):
    """Rebuild the students table when it still uses a single-column
    PRIMARY KEY(roll).

    The old schema (< multi-teacher support) declared roll as the sole
    primary key, so different teachers could never hold the same roll.
    Rebuild it as PRIMARY KEY (roll, teacher_id) to allow per-teacher
    data isolation while preserving existing (legacy) rows.
    """

    pk_columns = [
        r["name"]
        for r in conn.execute("PRAGMA table_info(students)").fetchall()
        if r["pk"]
    ]

    if pk_columns != ["roll"]:
        return

    conn.execute(
        """
        CREATE TABLE students_new (
            roll        INTEGER NOT NULL,
            name        TEXT NOT NULL,
            teacher_id  INTEGER,
            PRIMARY KEY (roll, teacher_id)
        )
        """
    )

    conn.execute(
        """
        INSERT INTO students_new (roll, name, teacher_id)
        SELECT roll, name, teacher_id FROM students
        """
    )

    conn.execute("DROP TABLE students")

    conn.execute("ALTER TABLE students_new RENAME TO students")

    conn.commit()


def _add_column_if_missing(conn, table, column, col_type):
    """ALTER TABLE to add a column if it does not already exist.

    SQLite cannot express 'ADD COLUMN IF NOT EXISTS', so inspect
    PRAGMA table_info() first and only ALTER when absent.
    """

    columns = [
        r["name"]
        for r in conn.execute(
            "PRAGMA table_info(" + table + ")"
        ).fetchall()
    ]

    if column in columns:
        return

    conn.execute(
        "ALTER TABLE " + table + " ADD COLUMN " + column + " " + col_type
    )

    conn.commit()


# ============================================================
# ===== TEACHERS =============================================
# ============================================================

def create_teacher(username, password_hash):
    """Insert a new teacher. Returns teacher_id or None if username exists."""

    conn = _get_connection()

    with _lock:

        exists = conn.execute(
            "SELECT id FROM teachers WHERE username = ?",
            (username,)
        ).fetchone()

        if exists is not None:
            return None

        cur = conn.execute(
            """
            INSERT INTO teachers (username, password_hash, created_at)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, date.today().isoformat())
        )

        conn.commit()

        return int(cur.lastrowid)


def get_teacher_by_username(username):
    """Return the teacher row dict or None."""

    conn = _get_connection()

    with _lock:

        row = conn.execute(
            "SELECT id, username, password_hash, created_at "
            "FROM teachers WHERE username = ?",
            (username,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "username": row["username"],
        "password_hash": row["password_hash"],
        "created_at": row["created_at"]
    }


def get_teacher_by_id(teacher_id):
    """Return teacher row dict or None."""

    try:
        teacher_id = int(teacher_id)
    except (TypeError, ValueError):
        return None

    conn = _get_connection()

    with _lock:

        row = conn.execute(
            "SELECT id, username, password_hash, created_at "
            "FROM teachers WHERE id = ?",
            (teacher_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "username": row["username"],
        "password_hash": row["password_hash"],
        "created_at": row["created_at"]
    }


def _migrate_legacy(conn):
    """One-time migration of legacy CSV/JSON files into SQLite."""

    # --- students ---
    if _table_empty(conn, "students") and os.path.exists(STUDENTS_FILE):
        legacy = _read_legacy_students()
        if legacy:
            conn.executemany(
                "INSERT OR IGNORE INTO students (roll, name) VALUES (?, ?)",
                [(s["roll"], s["name"]) for s in legacy]
            )

    # --- attendance ---
    if _table_empty(conn, "attendance_records") and os.path.exists(ATTENDANCE_FILE):
        legacy = _read_legacy_attendance()
        if legacy:
            for rec in legacy:
                _insert_record(conn, rec, None)

    # --- syllabus ---
    if _table_empty(conn, "syllabus_subjects") and os.path.exists(SYLLABUS_FILE):
        _migrate_legacy_syllabus(conn)

    conn.commit()


def _table_empty(conn, table):
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM " + table
    ).fetchone()
    return int(count["c"]) == 0


# ============================================================
# ===== LEGACY CSV/JSON READERS (migration only) ============
# ============================================================

def _read_legacy_students():
    """Read students from the legacy CSV (list of {roll, name})."""

    import csv

    result = []

    if not os.path.exists(STUDENTS_FILE):
        return result

    with open(STUDENTS_FILE, "r", encoding="utf-8", newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:

            roll = row.get("roll", "").strip()
            name = row.get("name", "").strip()

            if roll == "" or name == "":
                continue

            try:
                result.append({"roll": int(roll), "name": name})
            except (ValueError, TypeError):
                continue

    return result


def _read_legacy_attendance():
    """Read attendance from the legacy CSV."""

    import csv

    result = []

    if not os.path.exists(ATTENDANCE_FILE):
        return result

    with open(ATTENDANCE_FILE, "r", encoding="utf-8", newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:

            result.append({
                "date": row.get("date", "").strip(),
                "time": row.get("time", "").strip(),
                "roll": _to_int(row.get("roll", "")),
                "name": row.get("name", "").strip(),
                "status": row.get("status", "").strip(),
                "subject": row.get("subject", "").strip(),
                "lecture_type": row.get("lecture_type", "").strip()
            })

    return result


def _migrate_legacy_syllabus(conn):
    """Read the legacy syllabus.json and insert into relational tables."""

    if not os.path.exists(SYLLABUS_FILE):
        return

    try:

        with open(SYLLABUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    except (ValueError, OSError):
        return

    for subject in data.get("subjects", []):

        cur = conn.execute(
            "INSERT INTO syllabus_subjects (name) VALUES (?)",
            (subject.get("name", ""),)
        )
        subject_id = cur.lastrowid

        for unit in subject.get("units", []):

            cur = conn.execute(
                "INSERT INTO syllabus_units (subject_id, name) VALUES (?, ?)",
                (subject_id, unit.get("name", ""))
            )
            unit_id = cur.lastrowid

            for topic in unit.get("topics", []):

                conn.execute(
                    """
                    INSERT INTO syllabus_topics
                        (unit_id, title, completed, completed_date, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        unit_id,
                        topic.get("title", ""),
                        1 if topic.get("completed") else 0,
                        topic.get("completed_date"),
                        topic.get("notes", "")
                    )
                )


def _insert_record(conn, rec, session_id, teacher_id=None):
    """Insert one attendance record row."""

    conn.execute(
        """
        INSERT INTO attendance_records
            (session_id, date, time, roll, name, status,
             subject, lecture_type, attendance_mode, class_strength,
             teacher_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            rec.get("date", ""),
            rec.get("time", ""),
            rec.get("roll"),
            rec.get("name", ""),
            rec.get("status", ""),
            rec.get("subject", ""),
            rec.get("lecture_type", ""),
            rec.get("attendance_mode"),
            rec.get("class_strength"),
            teacher_id
        )
    )


def _upsert_session(conn, date_str, time_str, subject, lecture_type,
                    attendance_mode=None, class_strength=None,
                    teacher_id=None, session_uuid=None):
    """Insert or update the session row; return the session id.

    A legitimate attendance session is uniquely identified by its
    session_uuid (generated by the frontend for each intentional
    attendance run). Saving the SAME run again (e.g. accidental re-submit)
    updates that exact session; a brand-new run gets its own row even when
    it has the same minute-precision date/time/subject/lecture_type.

    For legacy/unknown callers that do not supply a session_uuid, fall
    back to the historical (date, time, subject, lecture_type, teacher_id)
    identity so duplicate-prevention still works for those clients.
    """

    if session_uuid:
        existing = conn.execute(
            """
            SELECT id FROM attendance_sessions
            WHERE session_uuid = ? AND teacher_id = ?
            """,
            (session_uuid, teacher_id)
        ).fetchone()
    else:
        existing = conn.execute(
            """
            SELECT id FROM attendance_sessions
            WHERE date = ? AND time = ? AND subject = ? AND lecture_type = ?
                  AND teacher_id = ?
            """,
            (date_str, time_str, subject, lecture_type, teacher_id)
        ).fetchone()

    if existing is not None:
        session_id = int(existing["id"])
        conn.execute(
            """
            UPDATE attendance_sessions
            SET attendance_mode = ?, class_strength = ?
            WHERE id = ?
            """,
            (attendance_mode, class_strength, session_id)
        )
        return session_id

    cur = conn.execute(
        """
        INSERT INTO attendance_sessions
            (date, time, subject, lecture_type, attendance_mode,
             class_strength, teacher_id, session_uuid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (date_str, time_str, subject, lecture_type,
         attendance_mode, class_strength, teacher_id, session_uuid)
    )
    return int(cur.lastrowid)


# ============================================================
# ===== STUDENTS ==============================================
# ============================================================

def get_students(teacher_id=None):
    """Return a list of dicts: {roll: int, name: str}, sorted by roll.

    If teacher_id is given, only that teacher's students are returned.
    """

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            rows = conn.execute(
                "SELECT roll, name FROM students "
                "WHERE teacher_id = ? ORDER BY roll",
                (teacher_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT roll, name FROM students ORDER BY roll"
            ).fetchall()

    return [
        {"roll": int(r["roll"]), "name": r["name"]}
        for r in rows
    ]


def get_student_by_roll(roll_number, teacher_id=None):
    """Return a student dict or None."""

    try:
        roll_number = int(roll_number)
    except (TypeError, ValueError):
        return None

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            row = conn.execute(
                "SELECT roll, name FROM students "
                "WHERE roll = ? AND teacher_id = ?",
                (roll_number, teacher_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT roll, name FROM students WHERE roll = ?",
                (roll_number,)
            ).fetchone()

    if row is None:
        return None

    return {"roll": int(row["roll"]), "name": row["name"]}


def replace_students(students, teacher_id=None):
    """Replace the whole student list.

    students: list of dicts {'roll': int, 'name': str}

    Returns: (saved_students, skipped_duplicates)
             skipped_duplicates = list of {'roll','name'} dropped because
             the roll already existed in the incoming list.
    """

    normalized = []
    seen = set()
    skipped = []

    for s in students:

        try:
            roll = int(str(s.get("roll")).strip())
        except (TypeError, ValueError):
            continue

        name = str(s.get("name", "")).strip()

        if name == "":
            continue

        if roll in seen:
            skipped.append({"roll": roll, "name": name})
            continue

        seen.add(roll)
        normalized.append({"roll": roll, "name": name})

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            conn.execute(
                "DELETE FROM students WHERE teacher_id = ?",
                (teacher_id,)
            )
        else:
            conn.execute("DELETE FROM students")

        conn.executemany(
            "INSERT INTO students (roll, name, teacher_id) VALUES (?, ?, ?)",
            [(s["roll"], s["name"], teacher_id) for s in normalized]
        )

        conn.commit()

    return normalized, skipped


def add_students(students, teacher_id=None):
    """Add new students, merging with existing ones.

    students: list of dicts {'roll': int, 'name': str}

    Returns: (saved_new, skipped_existing)
             skipped_existing = list of {'roll','name'} that already existed.
    """

    normalized = []
    seen = set()
    skipped = []

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            existing_rows = conn.execute(
                "SELECT roll FROM students WHERE teacher_id = ?",
                (teacher_id,)
            ).fetchall()
        else:
            existing_rows = conn.execute(
                "SELECT roll FROM students"
            ).fetchall()

        existing = {int(r["roll"]) for r in existing_rows}

        for s in students:

            try:
                roll = int(str(s.get("roll")).strip())
            except (TypeError, ValueError):
                continue

            name = str(s.get("name", "")).strip()

            if name == "":
                continue

            if roll in existing or roll in seen:
                skipped.append({"roll": roll, "name": name})
                continue

            seen.add(roll)
            normalized.append({"roll": roll, "name": name})

        if normalized:

            conn.executemany(
                "INSERT INTO students (roll, name, teacher_id) VALUES (?, ?, ?)",
                [(s["roll"], s["name"], teacher_id) for s in normalized]
            )

            conn.commit()

    return normalized, skipped


def delete_student(roll_number, teacher_id=None):
    """Remove one student by roll number.

    Returns True if a student was removed.
    """

    try:
        roll_number = int(roll_number)
    except (TypeError, ValueError):
        return False

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            cur = conn.execute(
                "DELETE FROM students WHERE roll = ? AND teacher_id = ?",
                (roll_number, teacher_id)
            )
        else:
            cur = conn.execute(
                "DELETE FROM students WHERE roll = ?",
                (roll_number,)
            )

        conn.commit()

    return cur.rowcount > 0


# ============================================================
# ===== ATTENDANCE ===========================================
# ============================================================

def _row_to_record(r):
    """Convert a sqlite Row into the flat record dict used by the app."""

    return {
        "session_id": r["session_id"],
        "date": r["date"],
        "time": r["time"],
        "roll": r["roll"],
        "name": r["name"] if r["name"] is not None else "",
        "status": r["status"],
        "subject": r["subject"],
        "lecture_type": r["lecture_type"],
        "attendance_mode": r["attendance_mode"],
        "class_strength": r["class_strength"],
    }


def save_attendance_session(records, attendance_mode=None,
                           class_strength=None, teacher_id=None,
                           session_uuid=None):
    """Append a full attendance session.

    records: list of dicts with keys:
             date, time, roll, name, status, subject
             (lecture_type optional, defaults to 'Theory')
    attendance_mode: 'file_upload' | 'class_strength' (optional metadata)
    class_strength:  int (optional metadata for class-strength mode)
    session_uuid:    client-generated id for this intentional attendance
                     run (optional; legacy callers without it keep the
                     historical date+time+subject+lecture_type identity)

    Returns the updated attendance records.
    """

    if not records:
        return get_attendance(teacher_id)

    conn = _get_connection()

    with _lock:

        first = records[0]

        session_date = str(first.get("date", ""))
        session_time = str(first.get("time", ""))
        subject = str(first.get("subject", "General"))
        lecture_type = str(first.get("lecture_type", "Theory"))

        session_id = _upsert_session(
            conn,
            session_date,
            session_time,
            subject,
            lecture_type,
            attendance_mode=attendance_mode,
            class_strength=class_strength,
            teacher_id=teacher_id,
            session_uuid=session_uuid
        )

        # Duplicate prevention: if this exact session (date + time +
        # subject + lecture_type) was already saved, remove its previous
        # records and replace them with the current ones. This stops the
        # same session creating duplicate attendance rows, without ever
        # touching historical sessions from other dates/times.
        conn.execute(
            "DELETE FROM attendance_records WHERE session_id = ?",
            (session_id,)
        )

        for rec in records:

            _insert_record(conn, rec, session_id, teacher_id)

        conn.commit()

    return get_attendance(teacher_id)


def get_attendance(teacher_id=None):
    """Return all attendance records for reporting."""

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            rows = conn.execute(
                """
                SELECT session_id, date, time, roll, name, status,
                       subject, lecture_type, attendance_mode, class_strength
                FROM attendance_records
                WHERE teacher_id = ?
                """,
                (teacher_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT session_id, date, time, roll, name, status,
                       subject, lecture_type, attendance_mode, class_strength
                FROM attendance_records
                """
            ).fetchall()

    return [_row_to_record(r) for r in rows]


def get_attendance_sessions(teacher_id=None):
    """Return attendance session metadata (date, time, subject, mode, strength)."""

    conn = _get_connection()

    with _lock:

        if teacher_id is not None:
            rows = conn.execute(
                """
                SELECT date, time, subject, lecture_type,
                       attendance_mode, class_strength
                FROM attendance_sessions
                WHERE teacher_id = ?
                ORDER BY date DESC, time DESC
                """,
                (teacher_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT date, time, subject, lecture_type,
                       attendance_mode, class_strength
                FROM attendance_sessions
                ORDER BY date DESC, time DESC
                """
            ).fetchall()

    return [
        {
            "date": r["date"],
            "time": r["time"],
            "subject": r["subject"],
            "lecture_type": r["lecture_type"],
            "attendance_mode": r["attendance_mode"],
            "class_strength": r["class_strength"]
        }
        for r in rows
    ]


def _to_int(value):
    """Safely convert a value to int, or None."""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ============================================================
# ===== SYLLABUS =============================================
# ============================================================

def _build_syllabus_tree(conn):
    """Read the relational syllabus tables back into the nested dict form."""

    subjects = []

    subject_rows = conn.execute(
        "SELECT id, name FROM syllabus_subjects ORDER BY id"
    ).fetchall()

    for sr in subject_rows:

        units = []

        unit_rows = conn.execute(
            "SELECT id, name FROM syllabus_units WHERE subject_id = ? ORDER BY id",
            (sr["id"],)
        ).fetchall()

        for ur in unit_rows:

            topics = []

            topic_rows = conn.execute(
                """
                SELECT id, title, completed, completed_date, notes
                FROM syllabus_topics WHERE unit_id = ? ORDER BY id
                """,
                (ur["id"],)
            ).fetchall()

            for tr in topic_rows:

                topics.append({
                    "id": tr["id"],
                    "title": tr["title"],
                    "completed": bool(tr["completed"]),
                    "completed_date": tr["completed_date"],
                    "notes": tr["notes"] if tr["notes"] is not None else ""
                })

            units.append({
                "id": ur["id"],
                "name": ur["name"],
                "topics": topics
            })

        subjects.append({
            "id": sr["id"],
            "name": sr["name"],
            "units": units
        })

    return {"subjects": subjects}


def get_syllabus():
    """Return the syllabus structure."""

    conn = _get_connection()

    with _lock:
        return _build_syllabus_tree(conn)


def add_subject(name):
    """Add a subject. Returns (success, message/subject)."""

    name = str(name or "").strip()

    if name == "":
        return False, "Subject name is required."

    conn = _get_connection()

    with _lock:

        exists = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE name = ?",
            (name,)
        ).fetchone()

        if exists is not None:
            return False, "Subject already exists."

        cur = conn.execute(
            "INSERT INTO syllabus_subjects (name) VALUES (?)",
            (name,)
        )

        subject_id = int(cur.lastrowid)

        conn.commit()

        subject = {
            "id": subject_id,
            "name": name,
            "units": []
        }

    return True, subject


def add_unit(subject_id, unit_name):
    """Add a unit to a subject. Returns (success, message/unit)."""

    unit_name = str(unit_name or "").strip()

    if unit_name == "":
        return False, "Unit name is required."

    conn = _get_connection()

    with _lock:

        subject = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE id = ?",
            (int(subject_id),)
        ).fetchone()

        if subject is None:
            return False, "Subject not found."

        cur = conn.execute(
            "INSERT INTO syllabus_units (subject_id, name) VALUES (?, ?)",
            (int(subject_id), unit_name)
        )

        unit_id = int(cur.lastrowid)

        conn.commit()

        unit = {"id": unit_id, "name": unit_name, "topics": []}

    return True, unit


def add_topic(subject_id, unit_id, topic_title):
    """Add a topic to a unit. Returns (success, message/topic)."""

    topic_title = str(topic_title or "").strip()

    if topic_title == "":
        return False, "Topic title is required."

    conn = _get_connection()

    with _lock:

        subject = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE id = ?",
            (int(subject_id),)
        ).fetchone()

        if subject is None:
            return False, "Subject not found."

        unit = conn.execute(
            "SELECT id FROM syllabus_units WHERE id = ?",
            (int(unit_id),)
        ).fetchone()

        if unit is None:
            return False, "Unit not found."

        cur = conn.execute(
            "INSERT INTO syllabus_topics (unit_id, title) VALUES (?, ?)",
            (int(unit_id), topic_title)
        )

        topic_id = int(cur.lastrowid)

        conn.commit()

        topic = {
            "id": topic_id,
            "title": topic_title,
            "completed": False,
            "completed_date": None,
            "notes": ""
        }

    return True, topic


def toggle_topic(subject_id, unit_id, topic_id):
    """Mark a topic completed (record date) or pending."""

    conn = _get_connection()

    with _lock:

        subject = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE id = ?",
            (int(subject_id),)
        ).fetchone()

        if subject is None:
            return False, "Subject not found."

        unit = conn.execute(
            "SELECT id FROM syllabus_units WHERE id = ?",
            (int(unit_id),)
        ).fetchone()

        if unit is None:
            return False, "Unit not found."

        topic = conn.execute(
            "SELECT id, completed FROM syllabus_topics WHERE id = ?",
            (int(topic_id),)
        ).fetchone()

        if topic is None:
            return False, "Topic not found."

        new_completed = not bool(topic["completed"])

        conn.execute(
            """
            UPDATE syllabus_topics
            SET completed = ?, completed_date = ?
            WHERE id = ?
            """,
            (
                1 if new_completed else 0,
                date.today().isoformat() if new_completed else None,
                int(topic_id)
            )
        )

        conn.commit()

        result_topic = {
            "id": int(topic_id),
            "completed": new_completed,
            "completed_date": (
                date.today().isoformat() if new_completed else None
            )
        }

    return True, result_topic


def update_topic_notes(subject_id, unit_id, topic_id, notes):
    """Save notes for a topic."""

    conn = _get_connection()

    with _lock:

        subject = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE id = ?",
            (int(subject_id),)
        ).fetchone()

        if subject is None:
            return False, "Subject not found."

        unit = conn.execute(
            "SELECT id FROM syllabus_units WHERE id = ?",
            (int(unit_id),)
        ).fetchone()

        if unit is None:
            return False, "Unit not found."

        topic = conn.execute(
            "SELECT id FROM syllabus_topics WHERE id = ?",
            (int(topic_id),)
        ).fetchone()

        if topic is None:
            return False, "Topic not found."

        conn.execute(
            "UPDATE syllabus_topics SET notes = ? WHERE id = ?",
            (str(notes or ""), int(topic_id))
        )

        conn.commit()

        result_topic = {
            "id": int(topic_id),
            "notes": str(notes or "")
        }

    return True, result_topic


def delete_subject(subject_id):
    """Delete a subject and its units/topics."""

    conn = _get_connection()

    with _lock:

        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            return False

        subject = conn.execute(
            "SELECT id FROM syllabus_subjects WHERE id = ?",
            (subject_id,)
        ).fetchone()

        if subject is None:
            return False

        # Delete child rows (units then their topics)
        unit_ids = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM syllabus_units WHERE subject_id = ?",
                (subject_id,)
            ).fetchall()
        ]

        for uid in unit_ids:
            conn.execute(
                "DELETE FROM syllabus_topics WHERE unit_id = ?",
                (uid,)
            )

        conn.execute(
            "DELETE FROM syllabus_units WHERE subject_id = ?",
            (subject_id,)
        )

        conn.execute(
            "DELETE FROM syllabus_subjects WHERE id = ?",
            (subject_id,)
        )

        conn.commit()

    return True


# ============================================================
# ===== HELPER: SYLLABUS SUMMARY =============================
# ============================================================

def syllabus_summary(data=None):
    """Return total/completed/pending topic counts and percentage."""

    if data is None:
        data = get_syllabus()

    total = 0
    completed = 0

    for subject in data["subjects"]:

        for unit in subject.get("units", []):

            for topic in unit.get("topics", []):

                total += 1

                if topic.get("completed"):
                    completed += 1

    percentage = (
        round((completed / total) * 100, 1)
        if total > 0
        else 0
    )

    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
        "percentage": percentage
    }
