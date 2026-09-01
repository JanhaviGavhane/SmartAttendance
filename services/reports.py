

# ===== REPORTS SERVICE =====
#
# Computes attendance statistics used by the Reports page,
# the Dashboard, and the Calendar page.

import csv
import io
from datetime import date

from . import storage as _storage
from .storage import (
    get_students,
    get_attendance,
    get_syllabus,
    syllabus_summary
)


# ============================================================
# ===== SUMMARY ==============================================
# ============================================================

def session_summaries(records):
    """Group attendance records by (date, subject, lecture_type).

    Returns a list of session dicts:
    {
      date, subject, lecture_type,
      time,           # first record's time
      present, absent, total, percentage
    }
    """

    sessions = {}

    for r in records:

        key = (
            r.get("date", ""),
            r.get("subject", ""),
            r.get("lecture_type", "")
        )

        if key not in sessions:

            sessions[key] = {
                "date": r["date"],
                "subject": r.get("subject", ""),
                "lecture_type": r.get("lecture_type", ""),
                "time": r.get("time", ""),
                "present": 0,
                "absent": 0
            }

        if r.get("status") == "Present":

            sessions[key]["present"] += 1

        elif r.get("status") == "Absent":

            sessions[key]["absent"] += 1

    result = []

    for key, sess in sessions.items():

        sess["total"] = sess["present"] + sess["absent"]
        sess["percentage"] = (
            round((sess["present"] / sess["total"]) * 100, 1)
            if sess["total"] > 0
            else 0
        )

        result.append(sess)

    # Most recent first
    result.sort(key=lambda s: (s["date"], s["time"]), reverse=True)

    return result


def overall_summary(records):
    """Simple counts across all attendance records."""

    present = sum(1 for r in records if r.get("status") == "Present")
    absent = sum(1 for r in records if r.get("status") == "Absent")
    total = present + absent

    return {
        "present": present,
        "absent": absent,
        "total": total,
        "percentage": (
            round((present / total) * 100, 1)
            if total > 0
            else 0
        )
    }


# ============================================================
# ===== STUDENT-WISE =========================================
# ============================================================

def student_attendance(records):
    """Per-student attendance across all sessions.

    Returns a dict: roll -> {roll, name, present, absent, total, percentage}
    Only includes rolls that appear in the attendance records.
    """

    stats = {}

    for r in records:

        roll = r.get("roll")

        if roll is None:
            continue

        if roll not in stats:

            stats[roll] = {
                "roll": roll,
                "name": r.get("name", ""),
                "present": 0,
                "absent": 0
            }

        if r.get("status") == "Present":

            stats[roll]["present"] += 1

        elif r.get("status") == "Absent":

            stats[roll]["absent"] += 1

    result = list(stats.values())

    for s in result:

        s["total"] = s["present"] + s["absent"]
        s["percentage"] = (
            round((s["present"] / s["total"]) * 100, 1)
            if s["total"] > 0
            else 0
        )

    return result


def below_threshold(records, threshold=75.0):
    """Students whose attendance percentage is below the threshold."""

    result = []

    for s in student_attendance(records):

        if s["total"] > 0 and s["percentage"] < threshold:

            result.append(s)

    result.sort(key=lambda s: s["percentage"])

    return result


def frequently_absent(records, threshold_absent=3):
    """Students absent in many sessions (default: 3+ absences)."""

    result = []

    for s in student_attendance(records):

        if s["absent"] >= threshold_absent:

            result.append(s)

    result.sort(key=lambda s: s["absent"], reverse=True)

    return result


# ============================================================
# ===== FILTERS ==============================================
# ============================================================

def filter_records(records, date_from=None, date_to=None,
                   subject=None, lecture_type=None, roll=None):
    """Filter records by the given optional filters."""

    records = list(records)

    if date_from:
        records = [r for r in records if r.get("date", "") >= date_from]

    if date_to:
        records = [r for r in records if r.get("date", "") <= date_to]

    if subject:
        records = [
            r for r in records
            if (r.get("subject") or "").lower() == subject.lower()
        ]

    if lecture_type:
        records = [
            r for r in records
            if (r.get("lecture_type") or "").lower() == lecture_type.lower()
        ]

    if roll is not None:
        records = [r for r in records if r.get("roll") == int(roll)]

    return records


# ============================================================
# ===== DATE-WISE ============================================
# ============================================================

def date_wise(records):
    """Attendance grouped by date."""

    by_date = {}

    for r in records:

        d = r.get("date", "")

        if d not in by_date:

            by_date[d] = {"present": 0, "absent": 0}

        if r.get("status") == "Present":

            by_date[d]["present"] += 1

        elif r.get("status") == "Absent":

            by_date[d]["absent"] += 1

    result = []

    for d, counts in by_date.items():

        total = counts["present"] + counts["absent"]

        result.append({
            "date": d,
            "present": counts["present"],
            "absent": counts["absent"],
            "total": total,
            "percentage": (
                round((counts["present"] / total) * 100, 1)
                if total > 0
                else 0
            )
        })

    result.sort(key=lambda x: x["date"], reverse=True)

    return result


# ============================================================
# ===== DASHBOARD ============================================
# ============================================================

def dashboard_stats(teacher_id=None):
    """All stats needed by the dashboard."""

    students = _storage.get_students(teacher_id)
    records = _storage.get_attendance(teacher_id)

    today = date.today().isoformat()

    todays = [
        r for r in records if r.get("date") == today
    ]

    todays_summary = overall_summary(todays)
    overall = overall_summary(records)

    recent_sessions = session_summaries(records)[:5]

    syllabus = _storage.get_syllabus()
    syllabus_stats = _storage.syllabus_summary(syllabus)

    return {
        "total_students": len(students),
        "today": {
            "date": today,
            "present": todays_summary["present"],
            "absent": todays_summary["absent"],
            "total": todays_summary["total"],
            "percentage": todays_summary["percentage"],
            "sessions": session_summaries(todays)
        },
        "overall": overall,
        "recent_sessions": recent_sessions,
        "syllabus": syllabus_stats,
        "students": students
    }


# ============================================================
# ===== CSV EXPORT ===========================================
# ============================================================

def students_csv(teacher_id=None):
    """CSV string of all students."""

    buffer = io.StringIO()

    writer = csv.writer(buffer)

    writer.writerow(["Roll Number", "Student Name"])

    for s in _storage.get_students(teacher_id):

        writer.writerow([s["roll"], s["name"]])

    return buffer.getvalue()


def attendance_csv(records=None, teacher_id=None):
    """CSV string of attendance records (optionally filtered)."""

    if records is None:
        records = _storage.get_attendance(teacher_id)

    buffer = io.StringIO()

    writer = csv.writer(buffer)

    writer.writerow([
        "Date", "Time", "Roll Number", "Student Name",
        "Status", "Subject", "Lecture Type"
    ])

    for r in records:

        writer.writerow([
            r.get("date", ""),
            r.get("time", ""),
            r.get("roll", ""),
            r.get("name", ""),
            r.get("status", ""),
            r.get("subject", ""),
            r.get("lecture_type", "")
        ])

    return buffer.getvalue()


def report_csv(teacher_id=None):
    """CSV of the student-wise attendance report."""

    buffer = io.StringIO()

    writer = csv.writer(buffer)

    writer.writerow([
        "Roll Number", "Student Name", "Present",
        "Absent", "Total", "Percentage"
    ])

    for s in student_attendance(_storage.get_attendance(teacher_id)):

        writer.writerow([
            s["roll"], s["name"], s["present"],
            s["absent"], s["total"], str(s["percentage"]) + "%"
        ])

    return buffer.getvalue()

