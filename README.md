# Smart Attendance

A local, offline voice-based attendance system for teachers. Teachers register their own accounts, upload the class student list, and mark attendance by speaking roll numbers aloud — the browser captures audio, Vosk converts speech to text, and a clean Present/Absent record is generated and saved.

## Features

- **Voice-based attendance** using [Vosk](https://alphacephei.com/vosk/) — fully local and offline, no API keys or internet required
- **Teacher login / register** — each teacher creates an account; data is isolated per teacher
- **Student file upload** — upload the class list as `.xlsx`, `.xls`, `.docx`, or `.csv`
- **File-upload attendance mode** — attendance is taken against the exact student list uploaded for that session
- **Class-strength attendance mode** — type the total class strength and mark attendance without a file
- **Present / absent calculation** — every student gets exactly one status per session (Present or Absent); duplicates are ignored
- **Attendance saving and reports** — save sessions, download results in Excel/Word/CSV, and view dashboard and report pages
- **Syllabus tracking** — add subjects, units, and topics, mark topics complete, and attach notes
- **Calendar view** — see attendance history on a calendar

## Technologies

| Component | Technology |
|---|---|
| Backend | Python 3.12, Flask |
| Database | SQLite (auto-created on first run) |
| Speech recognition | Vosk (local, offline) + PyAV for audio decoding |
| Student file parsing | openpyxl (.xlsx), xlrd (.xls), python-docx (.docx), stdlib csv |
| Reports | pandas, openpyxl, python-docx |
| Frontend | HTML, CSS, vanilla JavaScript |
| Audio capture | Browser MediaRecorder (WebM/Opus) → Vosk |

See [requirements.txt](requirements.txt) for the exact pinned dependency list.

## Project structure

```
SmartAttendance/
├── app.py                          # Flask application (all routes)
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Pytest configuration
├── .gitignore                      # Git ignore rules (runtime data excluded)
├── services/
│   ├── storage.py                  # SQLite schema + teacher/data access
│   ├── vosk_service.py             # Vosk speech-to-text + roll number parsing
│   ├── student_parser.py           # Student file parsing (.xlsx/.xls/.docx/.csv)
│   ├── attendance_output.py        # Attendance result file generation
│   └── reports.py                  # Report/count aggregation
├── templates/                      # Jinja2 HTML templates (login, dashboard,
│                                   #   attendance, students, reports, syllabus,
│                                   #   calendar, settings, register)
├── static/
│   ├── css/                        # Stylesheets
│   └── js/                         # Frontend JavaScript
├── tests/                          # Automated pytest suite
│   ├── conftest.py                 # Isolated temp-DB fixtures
│   └── test_01_startup.py ...      # Tests (see "Running the tests")
│       test_16_pages.py
├── models/
│   └── vosk-model-small-en-us-0.15 # Vosk speech model (included in repo)
├── data/                           # Runtime data (auto-created, gitignored)
│   ├── smart_attendance.db         # SQLite database (created on first run)
│   ├── students.csv / attendance.csv / syllabus.json
│   └── uploads/                    # Temporary uploads + attendance results
└── venv/                           # Local virtual environment (gitignored)
```

## Setup for a new user

1. **Clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/SmartAttendance.git
   cd SmartAttendance
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment (Windows):**

   ```powershell
   venv\Scripts\activate
   ```

4. **Install the requirements:**

   ```bash
   pip install -r requirements.txt
   ```

   This installs Flask, Vosk, PyAV, pandas, openpyxl, python-docx, xlrd, soundfile,
   sounddevice, PyAudio, onnxruntime, and pytest.

   > **Note on PyAudio:** if `pip install -r requirements.txt` reports an error building
   > PyAudio on Windows, install the prebuilt wheel first, then continue:
   > `pip install PyAudio` usually resolves from PyPI wheels; alternatively use
   > `pip install --only-binary :all: PyAudio`. See [Troubleshooting](#troubleshooting).

5. **Vosk model.**

   Vosk needs a language model to transcribe speech. The required model
   **`vosk-model-small-en-us-0.15` is already included** in the `models/` folder of
   this repository (~68 MB), so no additional download is needed.
   `services/vosk_service.py` looks for `models/vosk-model-small-en-us-0.15`
   automatically. Keep the folder in place — the voice feature depends on it.

6. **Start the application:**

   ```bash
   python app.py
   ```

   On the very first run the application automatically creates the `data/` folder
   and the SQLite database (`data/smart_attendance.db`) with all required tables —
   there is no manual database setup.

## Open the application

After starting Flask, open your browser at:

```
http://127.0.0.1:5000
```

You will see the login page. If you have not created an account yet, click
**Register** to create one.

## Creating an account and logging in

1. Open `http://127.0.0.1:5000`.
2. On the login page click **Register a new account**.
3. Choose a username, enter a password, and confirm it. Click **Register**.
4. You are logged in automatically and land on the Dashboard.
5. Next time, just enter your username and password on the login page.
6. Use the **Logout** button in the dashboard to end the session.

There are no pre-created accounts — every teacher registers their own.

## Attendance workflow

```
Register / Login → Students → Upload student list → Attendance →
select mode → Start Attendance → say roll numbers → Save Attendance → Reports
```

Step by step:

1. **Register / Login** to your teacher account.
2. **Students** — go to the Students page and **Upload Student List** (a `.csv`,
   `.xlsx`, `.xls` or `.docx` file). The master student list is stored for your
   account.
3. **Upload student file for this session** (optional) — either on the Students page
   or from the Attendance page itself. When you use **Voice attendance**, the list
   you upload is the exact one used for that session.
4. **Attendance** — open the Attendance page and pick a mode:
   - **Upload Student File** — attendance is taken against the file uploaded for
     this session (every student gets Present or Absent from exactly that list).
   - **Class Strength** — enter the total number of students in the class instead;
     absent is computed from the strength you provide.
   - **Voice Roll Call** — works with either mode.
5. **Start Attendance** — grant microphone permission when prompted.
6. **Say roll numbers** — read roll numbers aloud, e.g. "one", "five", "twenty
   five". Vosk transcribes them locally and marks each as Present. Detected
   students appear under **Present students**; anything not said stays Absent
   until you save.
7. **Save Attendance** — choose the subject and lecture type, then click
   **Save Attendance**. The session is written to the database and an Excel/Word
   result file is generated and made available for download.
8. **Reports** — open the Reports page to view per-teacher attendance records,
   download CSV exports, and see counts on the Dashboard. The Calendar page shows
   when attendance was taken.

## Teacher data isolation

Every piece of data — the student list, attendance sessions, and attendance
records — is stored against the logged-in teacher. Each teacher:

- sees only their own students on the Students page,
- sees only their own attendance on the Reports page,
- can never see another teacher's students or attendance, even if usernames or
  roll numbers (e.g. roll `1`) are shared.

Attendance is scoped by the server session, not by anything the browser sends,
so swapping accounts cannot expose data from another teacher.

## Runtime data and Git

The `data/` folder (the SQLite database, student/attendance CSV files, syllabus
JSON, and uploaded files) is **runtime data, intentionally ignored by Git**
(`.gitignore`). This means:

- your local database and any test uploads are never committed,
- a fresh clone starts with a **clean, empty database**,
- tables are created automatically on the first run.

Only the code, templates, static assets, tests, and the bundled Vosk model are
committed.

## Supported student file formats

Based on the actual parser (`services/student_parser.py`):

| Format | How it is read |
|---|---|
| `.xlsx` | Excel workbooks via openpyxl (header row detected from the first rows) |
| `.xls` | Legacy Excel via xlrd |
| `.docx` | Word tables first, then line-based text (e.g. `1. Alice`, `1 Alice`) |
| `.csv` | UTF-8 (with optional BOM) via the stdlib csv module |

Column detection matches headers such as **Roll No / Roll# / Adm No / ID** for
rolls and **Student Name / Name / Candidate Name** for names. If no header is
found, the first two columns are used. Empty rows are skipped, duplicate rolls
are reported separately (not imported), and rolls outside `1–1000` or missing
names produce warnings. Students are stored sorted by roll number.

## Running the automated tests

Run the full test suite from the project root (with the virtual environment
activated):

```bash
pytest
```

All tests run against a **throwaway temporary database** — your real
`data/smart_attendance.db` is never touched.

What the tests cover (see `tests/` — `test_01_startup.py` … `test_16_pages.py`):

- **Startup**: tables are auto-created on first use; the schema is the current clean one
- **Login/register**: register → dashboard, valid/invalid login, logout
- **Teacher isolation**: students and attendance are scoped per teacher
- **Student upload**: CSV/XLSX/DOCX, invalid/empty files, duplicate rolls, rolls 1–100
- **Session reset**: no carry-over between attendance sessions
- **Class-strength mode**: correct present/absent/count, no stale retention
- **Duplicate handling**: a roll said twice is only marked present once
- **Roll parser**: valid (`one`, `twenty three`, `one hundred`) and invalid
  (`two three`, `101`, `200`) inputs
- **Vosk endpoint**: auth required, missing/invalid audio handling, valid WAV
- **Attendance save**: status mapping, Excel/Word result download, student-list
  requirement, original file never overwritten
- **Save button wiring**: frontend validations + backend save contract
- **Old-data regression**: no stale absent/strength leaks after fixes
- **Fresh install**: brand-new DB workflow from scratch, no hardcoded accounts
- **DB integrity**: required tables/FKs and teacher_id association
- **Pages**: protected pages redirect when logged out, render when logged in

## Troubleshooting

| Problem | Solution |
|---|---|
| **Vosk model not found / "model path does not exist"** | Make sure the `models/vosk-model-small-en-us-0.15` folder is present in the repo root (it is bundled). Do not move or rename it; `vosk_service.py` resolves it relative to the project. |
| **Microphone not working / No audio captured** | Allow microphone permission in the browser and use Chrome or Edge. Voice attendance needs a real microphone; check OS privacy settings that allow the browser access. |
| **Roll numbers not recognized** | Speak single digit ranges and clear names (e.g. "fifteen"). The small model works best with clear audio and low background noise. |
| **PyAudio fails to install** | On Windows, install the wheel explicitly first: `pip install PyAudio` — or use `pip install --only-binary :all: PyAudio` — then retry `pip install -r requirements.txt`. |
| **`flask` not recognized** | You are not in the virtual environment. Activate it first (`venv\Scripts\activate` on Windows), or run `venv\Scripts\python.exe app.py`. |
| **Port 5000 already in use** | Close the other process, or start the app on a different port by running Flask with another port (e.g. set the port in `app.run(...)` in `app.py`). |
| **Attendance page says "No student list loaded for this session"** | In **Upload Student File** mode you must upload the list for the session before saving. Use Class Strength mode (with `class_strength` set) if you do not want to upload a file. |
| **Data looks deleted / empty after restart** | Runtime data lives in `data/` and is gitignored; it is not committed. A fresh clone starts with an empty database by design (teachers just register again). |
| **`pytest` not found** | `pytest` is in `requirements.txt`; re-run `pip install -r requirements.txt` inside your activated venv. |

## Note on the Vosk model

The Vosk model is **required** for voice-based attendance. This repository
bundles `models/vosk-model-small-en-us-0.15` (~68 MB) so no separate download is
needed after cloning. Vosk runs entirely locally — no API keys, no internet, no
third-party services.

---

> **Privacy note:** all audio is processed locally by Vosk on your machine, and no
> audio files leave your computer.