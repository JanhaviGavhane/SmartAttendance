
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    Response,
    session,
    send_file
)

from functools import wraps
import secrets
import os
import uuid

from werkzeug.security import generate_password_hash, check_password_hash

from services.vosk_service import transcribe_audio, extract_roll_number
from services.storage import (
    ensure_data_folder,
    get_students,
    get_student_by_roll,
    replace_students,
    delete_student,
    get_attendance,
    save_attendance_session,
    get_syllabus,
    add_subject,
    add_unit,
    add_topic,
    toggle_topic,
    update_topic_notes,
    delete_subject,
    syllabus_summary,
    get_attendance_sessions,
    create_teacher,
    get_teacher_by_username,
    get_teacher_by_id,
    DATA_DIR,
    UPLOADS_DIR
)
from services.student_parser import (
    parse_student_file,
    SUPPORTED_EXTENSIONS
)
from services import reports as reports_service
from services import attendance_output


app = Flask(__name__)

app.secret_key = secrets.token_hex(32)


# ============================================================
# ===== LOGIN REQUIRED DECORATOR =============================
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "teacher_id" not in session:
            if (request.is_json or request.path.startswith("/api/") or
                    request.content_type and
                    "application/json" in request.content_type):
                return jsonify({"success": False,
                                "error": "Not logged in"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# Create the data folder/files if missing
ensure_data_folder()


# ============================================================
# ===== LOGIN PAGE ============================================
# ============================================================

@app.route("/")
def index():

    if "teacher_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ============================================================
# ===== LOGIN (GET shows the page, POST authenticates) ========
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        teacher = get_teacher_by_username(username)

        if teacher and check_password_hash(teacher["password_hash"], password):

            session["teacher_id"] = teacher["id"]
            session["username"] = teacher["username"]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    if "teacher_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# ============================================================
# ===== REGISTER ==============================================
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not username or not password:
            return render_template(
                "register.html",
                error="Username and password required."
            )

        if password != confirm:
            return render_template(
                "register.html",
                error="Passwords do not match."
            )

        if get_teacher_by_username(username):
            return render_template(
                "register.html",
                error="Username already exists."
            )

        teacher_id = create_teacher(
            username,
            generate_password_hash(password)
        )

        session["teacher_id"] = teacher_id
        session["username"] = username

        return redirect(url_for("dashboard"))

    return render_template("register.html")


# ============================================================
# ===== LOGOUT ================================================
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# ===== DASHBOARD =============================================
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    teacher_id = session.get("teacher_id")

    stats = reports_service.dashboard_stats(teacher_id)

    return render_template(
        "dashboard.html",
        stats=stats,
        today_display=_today_display()
    )


# ============================================================
# ===== ATTENDANCE ============================================
# ============================================================

@app.route("/attendance")
@login_required
def attendance():

    # The attendance page always starts with a clean, session-local
    # student list. It must NOT inject the global Students/master table
    # as the active list - that would re-activate the previous session's
    # uploaded file on every load. The active list is populated only
    # when the user uploads a file for THIS session (/session/students).
    return render_template(
        "attendance.html",
        students=[],
        has_students=False
    )


# ============================================================
# ===== STUDENTS ==============================================
# ============================================================

@app.route("/students")
@login_required
def students():

    teacher_id = session.get("teacher_id")

    student_list = get_students(teacher_id)

    return render_template(
        "students.html",
        students=student_list,
        total_students=len(student_list)
    )


# ============================================================
# ===== STUDENT UPLOAD ========================================
# ============================================================

@app.route(
    "/students/upload",
    methods=["POST"]
)
@login_required
def students_upload():

    teacher_id = session.get("teacher_id")

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    uploaded = request.files["file"]

    if uploaded.filename == "":

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    extension = os.path.splitext(uploaded.filename)[1].lower()

    if extension not in SUPPORTED_EXTENSIONS:

        return jsonify({
            "success": False,
            "error": "Unsupported file type. " +
                     "Use .xlsx, .xls, .docx or .csv."
        }), 400

    # Save the upload temporarily so we can parse it
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    temp_path = os.path.join(
        UPLOADS_DIR,
        "upload_" + str(uuid.uuid4()) + extension
    )

    uploaded.save(temp_path)

    try:

        parsed = parse_student_file(
            temp_path,
            filename=uploaded.filename
        )

        if not parsed["success"]:

            return jsonify({
                "success": False,
                "error": parsed["error"]
            }), 400

        # Store normalized student data safely
        replace_mode = (
            request.form.get("mode", "").strip().lower() == "replace"
        )

        if replace_mode:

            saved, skipped = replace_students(parsed["students"], teacher_id)

        else:

            # Merge with existing students; keep any new ones
            existing = get_students(teacher_id)
            existing_by_roll = {
                s["roll"]: s for s in existing
            }

            merged = list(existing)

            for s in parsed["students"]:

                if s["roll"] not in existing_by_roll:

                    merged.append(s)

            saved, skipped = replace_students(merged, teacher_id)

        return jsonify({
            "success": True,
            "message": parsed["message"],
            "students": saved,
            "duplicates": parsed["duplicates"],
            "empty_rows": parsed["empty_rows"],
            "errors": parsed["errors"],
            "skipped": skipped
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        if os.path.exists(temp_path):

            os.remove(temp_path)


# ============================================================
# ===== DELETE STUDENT ========================================
# ============================================================

@app.route(
    "/session/students",
    methods=["POST"]
)
@login_required
def session_students():
    """Parse an uploaded student file for the CURRENT attendance
    session WITHOUT writing anything to the permanent students table.

    The returned list is held only in the browser's session state so
    each attendance session uses exactly the file uploaded for it. The
    Students/master data on /students is intentionally not touched.
    """

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    uploaded = request.files["file"]

    if uploaded.filename == "":

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    extension = os.path.splitext(uploaded.filename)[1].lower()

    if extension not in SUPPORTED_EXTENSIONS:

        return jsonify({
            "success": False,
            "error": "Unsupported file type. " +
                     "Use .xlsx, .xls, .docx or .csv."
        }), 400

    temp_path = os.path.join(
        UPLOADS_DIR,
        "session_" + str(uuid.uuid4()) + extension
    )

    uploaded.save(temp_path)

    try:

        parsed = parse_student_file(
            temp_path,
            filename=uploaded.filename
        )

        if not parsed["success"]:

            return jsonify({
                "success": False,
                "error": parsed["error"]
            }), 400

        # Session-specific: return the parsed students to the browser.
        # We do NOT call replace_students()/get_students() here.
        return jsonify({
            "success": True,
            "message": parsed["message"],
            "students": parsed["students"],
            "duplicates": parsed["duplicates"],
            "empty_rows": parsed["empty_rows"],
            "errors": parsed["errors"]
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        if os.path.exists(temp_path):

            os.remove(temp_path)


# ============================================================
# ===== DELETE STUDENT ========================================
# ============================================================

@app.route(
    "/students/delete",
    methods=["POST"]
)
@login_required
def students_delete():

    teacher_id = session.get("teacher_id")

    roll = request.form.get("roll")

    if roll is None:

        return jsonify({
            "success": False,
            "error": "Roll number is required."
        }), 400

    removed = delete_student(roll, teacher_id)

    return jsonify({
        "success": removed,
        "error": None if removed else "Student not found.",
        "students": get_students(teacher_id)
    })


# ============================================================
# ===== STUDENT LIST API ======================================
# ============================================================

@app.route("/api/students")
@login_required
def api_students():

    teacher_id = session.get("teacher_id")

    return jsonify({
        "students": get_students(teacher_id)
    })


# ============================================================
# ===== SYLLABUS TRACKER =====================================
# ============================================================

@app.route("/syllabus")
@login_required
def syllabus():

    data = get_syllabus()

    return render_template(
        "syllabus.html",
        syllabus_data=data,
        syllabus_summary=syllabus_summary(data)
    )


# ============================================================
# ===== SYLLABUS API ==========================================
# ============================================================

@app.route("/api/syllabus")
@login_required
def api_syllabus():

    data = get_syllabus()

    return jsonify({
        "syllabus": data,
        "summary": syllabus_summary(data)
    })


@app.route("/syllabus/subject", methods=["POST"])
@login_required
def syllabus_add_subject():

    name = request.form.get("name")

    success, result = add_subject(name)

    if not success:

        return jsonify({
            "success": False,
            "error": result if isinstance(result, str) else str(result)
        }), 400

    return jsonify({
        "success": True,
        "subject": result,
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


@app.route("/syllabus/unit", methods=["POST"])
@login_required
def syllabus_add_unit():

    subject_id = request.form.get("subject_id")
    name = request.form.get("name")

    success, result = add_unit(subject_id, name)

    if not success:

        return jsonify({
            "success": False,
            "error": result if isinstance(result, str) else str(result)
        }), 400

    return jsonify({
        "success": True,
        "unit": result,
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


@app.route("/syllabus/topic", methods=["POST"])
@login_required
def syllabus_add_topic():

    subject_id = request.form.get("subject_id")
    unit_id = request.form.get("unit_id")
    title = request.form.get("title")

    success, result = add_topic(subject_id, unit_id, title)

    if not success:

        return jsonify({
            "success": False,
            "error": result if isinstance(result, str) else str(result)
        }), 400

    return jsonify({
        "success": True,
        "topic": result,
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


@app.route("/syllabus/topic/toggle", methods=["POST"])
@login_required
def syllabus_toggle_topic():

    subject_id = request.form.get("subject_id")
    unit_id = request.form.get("unit_id")
    topic_id = request.form.get("topic_id")

    success, result = toggle_topic(subject_id, unit_id, topic_id)

    if not success:

        return jsonify({
            "success": False,
            "error": result if isinstance(result, str) else str(result)
        }), 400

    return jsonify({
        "success": True,
        "topic": result,
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


@app.route("/syllabus/topic/notes", methods=["POST"])
@login_required
def syllabus_topic_notes():

    subject_id = request.form.get("subject_id")
    unit_id = request.form.get("unit_id")
    topic_id = request.form.get("topic_id")
    notes = request.form.get("notes", "")

    success, result = update_topic_notes(
        subject_id, unit_id, topic_id, notes
    )

    if not success:

        return jsonify({
            "success": False,
            "error": result if isinstance(result, str) else str(result)
        }), 400

    return jsonify({
        "success": True,
        "topic": result,
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


@app.route("/syllabus/subject", methods=["DELETE"])
@login_required
def syllabus_delete_subject():

    subject_id = request.args.get("subject_id")

    removed = delete_subject(subject_id)

    return jsonify({
        "success": removed,
        "error": None if removed else "Subject not found.",
        "syllabus": get_syllabus(),
        "summary": syllabus_summary(get_syllabus())
    })


# ============================================================
# ===== REPORTS ===============================================
# ============================================================

@app.route("/reports")
@login_required
def reports():

    return render_template(
        "reports.html"
    )


# ============================================================
# ===== REPORTS API ===========================================
# ============================================================

@app.route("/api/reports")
@login_required
def api_reports():

    teacher_id = session.get("teacher_id")

    records = reports_service.get_attendance(teacher_id)

    # Optional filters
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    subject = request.args.get("subject", "").strip()
    lecture_type = request.args.get("lecture_type", "").strip()
    roll = request.args.get("roll", "").strip()

    filtered = reports_service.filter_records(
        records,
        date_from=date_from or None,
        date_to=date_to or None,
        subject=subject or None,
        lecture_type=lecture_type or None,
        roll=(int(roll) if roll.isdigit() else None)
    )

    return jsonify({
        "students": reports_service.get_students(teacher_id),
        "records": filtered,
        "summary": reports_service.overall_summary(filtered),
        "student_attendance": reports_service.student_attendance(filtered),
        "date_wise": reports_service.date_wise(filtered),
        "sessions": reports_service.session_summaries(filtered),
        "below_threshold": reports_service.below_threshold(filtered, 75.0),
        "frequently_absent": reports_service.frequently_absent(filtered, 3),
        "subjects": sorted({
            r.get("subject", "") for r in records if r.get("subject")
        }),
        "lecture_types": sorted({
            r.get("lecture_type", "") for r in records if r.get("lecture_type")
        })
    })


@app.route("/reports/csv")
@login_required
def reports_csv():

    teacher_id = session.get("teacher_id")

    data = reports_service.report_csv(teacher_id)

    return Response(
        _bom() + data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=attendance_report.csv"
        }
    )


@app.route("/reports/attendance-csv")
@login_required
def reports_attendance_csv():

    teacher_id = session.get("teacher_id")

    data = reports_service.attendance_csv(
        get_attendance(teacher_id)
    )

    return Response(
        _bom() + data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=attendance_records.csv"
        }
    )


# ============================================================
# ===== CALENDAR ==============================================
# ============================================================

@app.route("/calendar")
@login_required
def calendar():

    return render_template(
        "calendar.html"
    )


@app.route("/api/calendar")
@login_required
def api_calendar():

    teacher_id = session.get("teacher_id")

    records = reports_service.get_attendance(teacher_id)

    return jsonify({
        "sessions": reports_service.session_summaries(records),
        "date_wise": reports_service.date_wise(records)
    })


# ============================================================
# ===== SETTINGS =============================================
# ============================================================

@app.route("/settings")
@login_required
def settings():

    return render_template(
        "settings.html"
    )


# ============================================================
# ===== SAVE ATTENDANCE SESSION ==============================
# ============================================================

@app.route(
    "/attendance/save",
    methods=["POST"]
)
@login_required
def attendance_save():

    teacher_id = session.get("teacher_id")

    data = request.get_json(silent=True)

    if not isinstance(data, dict):

        return jsonify({
            "success": False,
            "error": "Invalid request data."
        }), 400

    # Session details
    session_date = str(data.get("date", "")).strip()
    time_captured = str(data.get("time", "")).strip()
    subject = str(data.get("subject", "")).strip()
    lecture_type = str(data.get("lecture_type", "")).strip()

    # Attendance mode: 'file_upload' (default) or 'class_strength'
    attendance_mode = str(
        data.get("attendance_mode", "file_upload")
    ).strip().lower()

    if attendance_mode not in ("file_upload", "class_strength"):
        attendance_mode = "file_upload"

    class_strength = data.get("class_strength")

    try:
        class_strength = int(class_strength)
    except (TypeError, ValueError):
        class_strength = None

    # Roll numbers marked present
    present_rolls = data.get("present", [])

    if not isinstance(present_rolls, list):
        present_rolls = []

    # Roll numbers to mark absent (only used as a hint in file mode;
    # the authoritative absent set is computed from the source of truth
    # below so stale/old absent data can never leak in).
    absent_rolls = data.get("absent", [])

    if not isinstance(absent_rolls, list):
        absent_rolls = []

    if subject == "":
        subject = "General"

    if lecture_type not in ("Theory", "Practical", "Extra"):
        lecture_type = "Theory"

    # Validate class strength for class-strength mode.
    if attendance_mode == "class_strength":

        if class_strength is None or class_strength <= 0:

            return jsonify({
                "success": False,
                "error": "Class strength must be a positive number " +
                         "in class-strength mode."
            }), 400

    # Build a clean, ordered set of present rolls.
    present_set = set()
    present_ordered = []

    for roll in present_rolls:

        try:
            roll = int(roll)
        except (TypeError, ValueError):
            continue

        if roll in present_set:
            continue

        if attendance_mode == "class_strength" and roll > class_strength:
            # Out of the valid 1..class_strength range; skip.
            continue

        present_set.add(roll)
        present_ordered.append(roll)

    # ============================================================
    # SOURCE OF TRUTH for the student list + absent set
    # ============================================================
    # In FILE_UPLOAD mode the uploaded file for THIS session is the
    # source of truth. The frontend sends the current session's student
    # list in the payload ("students"), so attendance is always based on
    # exactly the list uploaded for this session - never stale global
    # data and never only the present rolls.
    #
    # If no session list is supplied (older clients), fall back to the
    # stored students table for backward compatibility.
    attempt_students = data.get("students")

    students_by_roll = {}

    if isinstance(attempt_students, list) and attempt_students:

        for s in attempt_students:

            try:
                roll = int(s.get("roll"))
            except (TypeError, ValueError):
                continue

            students_by_roll[roll] = {
                "roll": roll,
                "name": str(s.get("name") or "").strip()
            }

    if attendance_mode == "class_strength":

        # Absent = all rolls 1..class_strength that are not present.
        absent_ordered = [
            r for r in range(1, class_strength + 1)
            if r not in present_set
        ]

        # Present records only for detected rolls within range.
        present_allowed = present_ordered

    else:

        # file_upload: the uploaded file for THIS session is the source
        # of truth - every student in it gets exactly one status (Present
        # if detected, else Absent). A detected roll NOT in the session
        # list is ignored (it would be a fake student - never add it).
        # We never fall back to the global Students/master table, because
        # that would reuse a previous session's file as this session's
        # list.
        if not students_by_roll:

            return jsonify({
                "success": False,
                "error": "No student list loaded for this session. " +
                         "Upload a student file for this session first."
            }), 400

        present_allowed = [
            r for r in present_ordered
            if r in students_by_roll
        ]

        absent_ordered = [
            r for r in sorted(students_by_roll.keys())
            if r not in present_set
        ]

    # Build the record rows
    records = []

    # Present
    for roll in present_allowed:

        student = students_by_roll.get(roll)

        records.append(_build_record(
            session_date, time_captured, roll,
            student["name"] if student else "",
            "Present", subject, lecture_type,
            attendance_mode, class_strength
        ))

    # Absent
    for roll in absent_ordered:

        student = students_by_roll.get(roll)

        records.append(_build_record(
            session_date, time_captured, roll,
            student["name"] if student else "",
            "Absent", subject, lecture_type,
            attendance_mode, class_strength
        ))

    if not records:

        return jsonify({
            "success": False,
            "error": "No attendance records to save."
        }), 400

    save_attendance_session(
        records,
        attendance_mode=attendance_mode,
        class_strength=class_strength,
        teacher_id=teacher_id
    )

    # ============================================================
    # Generate an attendance-marked result file for this session.
    # Every student in the session's source list receives a status, so
    # the output file mirrors exactly what was saved to the database.
    # ============================================================
    result_students = [
        {
            "roll": r["roll"],
            "name": r.get("name") or "",
            "status": r.get("status") or "Absent"
        }
        for r in records
    ]

    # Format: preserve the uploaded file type where practical.
    # (.xls reads are written back as .xlsx because xlwt is unavailable.)
    original_filename = str(data.get("original_filename", "") or "")
    original_ext = os.path.splitext(original_filename)[1].lower().lstrip(".")

    if attendance_mode == "class_strength" or original_ext not in (
        "xlsx", "docx", "csv"
    ):
        output_fmt = "xlsx"
    else:
        output_fmt = original_ext

    output_io, out_filename, out_mimetype = (
        attendance_output.generate_attendance_file(
            result_students,
            output_fmt,
            base_name=original_filename
        )
    )

    # Store under a unique name so separate sessions never overwrite
    # each other (uuid plus short timestamp).
    results_dir = os.path.join(UPLOADS_DIR, "attendance_results")
    os.makedirs(results_dir, exist_ok=True)

    unique_name = (
        time_captured.replace(":", "-").replace(" ", "_") + "_" +
        str(uuid.uuid4())[:8] + "_" + out_filename
    )

    stored_path = os.path.join(results_dir, unique_name)

    with open(stored_path, "wb") as handle:
        handle.write(output_io.getvalue())

    download_url = url_for("attendance_result", filename=unique_name)

    return jsonify({
        "success": True,
        "message": "Attendance saved (" + str(len(records)) +
                   " records).",
        "attendance_mode": attendance_mode,
        "class_strength": class_strength,
        "present_count": len(present_allowed),
        "absent_count": len(absent_ordered),
        "records": records,
        "download_url": download_url,
        "filename": unique_name,
        "format": output_fmt
    })


def _build_record(session_date, time_captured, roll, name, status,
                  subject, lecture_type, attendance_mode, class_strength):
    """Build a record dict."""

    record = {
        "date": session_date,
        "time": time_captured,
        "roll": roll,
        "name": name,
        "status": status,
        "subject": subject,
        "lecture_type": lecture_type,
        "attendance_mode": attendance_mode,
        "class_strength": class_strength,
    }

    return record


# ============================================================
# ===== ATTENDANCE RESULT DOWNLOAD ============================
# ============================================================

@app.route("/attendance/result/<path:filename>")
@login_required
def attendance_result(filename):
    """Serve a generated attendance result file for download."""

    import re

    # Defend against path traversal: only a plain filename inside the
    # attendance_results folder is allowed.
    safe = os.path.basename(filename)

    if not re.match(r"^[A-Za-z0-9_.\-]+$", safe):

        return "Invalid filename.", 400

    results_dir = os.path.join(UPLOADS_DIR, "attendance_results")

    file_path = os.path.join(results_dir, safe)

    if not os.path.isfile(file_path):

        return "File not found.", 404

    _, ext = os.path.splitext(safe)

    mimetypes = {
        ".xlsx": "application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument."
                 "wordprocessingml.document",
        ".csv": "text/csv"
    }

    return send_file(
        file_path,
        mimetype=mimetypes.get(ext, "application/octet-stream"),
        as_attachment=True,
        download_name=safe
    )


# ============================================================
# ===== VOSK TRANSCRIPTION (OFFLINE) =========================
# ============================================================

@app.route(
    "/transcribe",
    methods=["POST"]
)
@login_required
def transcribe():

    # Check whether audio was received
    if "audio" not in request.files:

        return jsonify({
            "success": False,
            "error": "No audio received"
        }), 400


    audio_file = request.files["audio"]


    # --------------------------------------------------------
    # Create temporary folder
    # --------------------------------------------------------

    temp_folder = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "temp"
    )

    os.makedirs(
        temp_folder,
        exist_ok=True
    )


    # --------------------------------------------------------
    # Create unique temporary filename
    # --------------------------------------------------------

    filename = (
        "audio_" +
        str(uuid.uuid4()) +
        ".webm"
    )


    filepath = os.path.join(
        temp_folder,
        filename
    )


    # --------------------------------------------------------
    # Save browser audio temporarily
    # --------------------------------------------------------

    audio_file.save(
        filepath
    )


    try:

        # ----------------------------------------------------
        # Transcribe with Vosk (local, offline, no API key)
        # ----------------------------------------------------

        text = transcribe_audio(
            filepath
        )

        roll_number = extract_roll_number(
            text
        )


        print(
            "Vosk heard:",
            repr(text),
            "| Roll:",
            roll_number
        )


        # ----------------------------------------------------
        # Send result back to JavaScript
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "text": text,

            "roll_number": roll_number

        })


    except Exception as error:

        print(
            "Vosk error:",
            error
        )


        return jsonify({

            "success": False,

            "error": str(error)

        }), 500


    finally:

        # ----------------------------------------------------
        # Delete temporary audio file
        # ----------------------------------------------------

        if os.path.exists(filepath):

            os.remove(filepath)


# ============================================================
# ===== HELPERS ===============================================
# ============================================================

def _today_display():
    """Return a friendly date string like '29 Aug 2026, Saturday'."""

    from datetime import datetime

    now = datetime.now()

    return now.strftime("%d %b %Y, %A")


def _bom():
    """UTF-8 BOM so Excel opens the CSV correctly."""

    return "\ufeff"


# ============================================================
# ===== RUN FLASK =============================================
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
