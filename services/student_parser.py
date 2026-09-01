

# ===== STUDENT FILE PARSER =====
#
# Parses teacher-uploaded student lists from:
#   - Excel .xlsx   (openpyxl)
#   - Excel .xls    (xlrd)
#   - Word  .docx   (python-docx)
#
# Extracts Roll Number and Student Name, validates duplicates,
# ignores empty rows, and reports errors for missing data.

import os
import re


# ============================================================
# ===== SUPPORTED EXTENSIONS =================================
# ============================================================

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".docx", ".csv"}


# ============================================================
# ===== COLUMN NAME MATCHING =================================
# ============================================================

_ROLL_KEYWORDS = [
    "roll number", "rollno", "roll no", "roll", "roll#",
    "adm no", "enrollment", "reg no", "student id", "id"
]

_NAME_KEYWORDS = [
    "student name", "name", "student", "full name",
    "students name", "candidate name"
]


def _matches_keywords(value, keywords):
    """Return True if the header value matches any keyword."""

    v = str(value).strip().lower()
    v = re.sub(r"[^a-z0-9# ]", " ", v)
    v = re.sub(r"\s+", " ", v).strip()

    for keyword in keywords:

        if v == keyword or v.startswith(keyword):

            return True

    return False


def _detect_columns(headers):
    """Given a header row, return (roll_index, name_index) or (None, None)."""

    roll_index = None
    name_index = None

    # First pass: exact keyword matching
    for i, header in enumerate(headers):

        if roll_index is None and _matches_keywords(header, _ROLL_KEYWORDS):
            roll_index = i

        if name_index is None and _matches_keywords(header, _NAME_KEYWORDS):
            name_index = i

    # Fallback: first two columns if headers are generic/empty
    if roll_index is None and name_index is None:

        if len(headers) >= 2:

            return 0, 1

    return roll_index, name_index


# ============================================================
# ===== NORMALIZE CELL VALUES ================================
# ============================================================

def _normalize_cell(value):
    """Convert a parsed cell to text, handling numbers/dates."""

    if value is None:
        return ""

    if isinstance(value, float):

        # Whole numbers -> no decimals
        if value.is_integer():

            return str(int(value))

        return str(value)

    if isinstance(value, int):

        return str(value)

    text = str(value).strip()

    return text


def _clean_name(name):
    """Clean a student name and reject obvious non-name values."""

    name = _normalize_cell(name)

    # Remove common column header artifacts like 'Student', 'Name'
    name = re.sub(r"^(student|name|full name)\s*[:]?\s*", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()

    return name


def _valid_roll(text):
    """Check whether a roll value is a plausible integer 1-1000."""

    digits = re.sub(r"\D", "", text)

    if not digits:
        return None

    try:

        value = int(digits)

    except ValueError:

        return None

    if 1 <= value <= 1000:

        return value

    return None


# ============================================================
# ===== EXCEL (.xlsx / .xls) =================================
# ============================================================

def _parse_excel(filepath):
    """Parse an Excel file. Returns list of raw rows (list of cells)."""

    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".xlsx":

        return _parse_xlsx(filepath)

    return _parse_xls(filepath)


def _parse_xlsx(filepath):
    """Parse .xlsx files using openpyxl."""

    from openpyxl import load_workbook

    workbook = load_workbook(
        filepath,
        read_only=True,
        data_only=True
    )

    rows = []

    for sheet in workbook.worksheets:

        for row in sheet.iter_rows(values_only=True):

            rows.append(list(row))

    workbook.close()

    return rows


def _parse_xls(filepath):
    """Parse legacy .xls files using xlrd."""

    import xlrd

    workbook = xlrd.open_workbook(filepath)

    rows = []

    for sheet in workbook.sheets():

        for row_index in range(sheet.nrows):

            rows.append(
                list(sheet.row_values(row_index))
            )

    return rows


# ============================================================
# ===== CSV (.csv) ===========================================
# ============================================================

def _parse_csv(filepath):
    """Parse a .csv file into rows of cells."""

    import csv

    rows = []

    with open(filepath, "r", encoding="utf-8-sig", newline="") as handle:

        reader = csv.reader(handle)

        for row in reader:
            rows.append(list(row))

    return rows


# ============================================================
# ===== WORD (.docx) =========================================
# ============================================================

def _parse_docx(filepath):
    """Parse a .docx file into rows.

    Word documents may store students as:
      - A Word table (preferred)
      - Lines of text like "1.  Alice" or "1 Alice"
      - Lines like "Alice - 12"

    We try tables first, then line-based fallback.
    """

    from docx import Document

    document = Document(filepath)

    rows = []

    # ---- Prefer tables ----
    tables_found = False

    for table in document.tables:

        if not tables_found:

            tables_found = True

        for row in table.rows:

            rows.append(
                [cell.text for cell in row.cells]
            )

    if tables_found and rows:
        return rows

    # ---- Fallback: line-based text ----
    lines = []

    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if text:
            lines.append(text)

    # A common format: "Roll No.<tab>Name" per line, or a list
    for line in lines:

        # Tabs or multiple spaces as separator
        if "\t" in line:

            parts = [p.strip() for p in line.split("\t")]

            rows.append(parts)

            continue

        # "1. Alice" / "1 - Alice" / "1 Alice"
        m = re.match(
            r"^\s*(\d{1,4})\s*[\.\-:)]?\s+(.+?)\s*$",
            line
        )

        if m:

            rows.append([m.group(1), m.group(2)])

            continue

        # Skip lines that look like headers
        marker = re.compile(
            r"^(roll|sr|no|sl|student|name)\b",
            re.IGNORECASE
        )

        if marker.match(line):
            continue

    return rows


# ============================================================
# ===== MAIN PARSE ENTRY POINT ===============================
# ============================================================

def parse_student_file(filepath, filename="", tabular_allowed=True):
    """Parse an uploaded student file.

    Returns a dict:
    {
      "success": bool,
      "error": str | None,
      "students": [ {roll, name}, ... ],      # valid unique rows
      "message": str,
      "duplicates": [ {roll, name}, ... ],    # duplicate rolls skipped
      "empty_rows": int,
      "errors": [ "row details", ... ]        # rows with missing data
    }
    """

    if not os.path.exists(filepath):

        return {
            "success": False,
            "error": "File not found.",
            "students": [],
            "message": "",
            "duplicates": [],
            "empty_rows": 0,
            "errors": []
        }

    extension = os.path.splitext(filepath)[1].lower()

    if extension not in SUPPORTED_EXTENSIONS:

        return {
            "success": False,
            "error": "Unsupported file type. Use .xlsx, .xls, .docx or .csv.",
            "students": [],
            "message": "",
            "duplicates": [],
            "empty_rows": 0,
            "errors": []
        }

    try:

        if extension == ".docx":

            rows = _parse_docx(filepath)

        elif extension == ".csv":

            rows = _parse_csv(filepath)

        else:

            rows = _parse_excel(filepath)

    except Exception as error:

        return {
            "success": False,
            "error": "Could not read the file: " + str(error),
            "students": [],
            "message": "",
            "duplicates": [],
            "empty_rows": 0,
            "errors": []
        }

    return _process_rows(rows, filename=filename)


def _process_rows(rows, filename=""):
    """Turn raw rows into validated student records."""

    if not rows:

        return {
            "success": False,
            "error": "The file is empty.",
            "students": [],
            "message": "",
            "duplicates": [],
            "empty_rows": 0,
            "errors": []
        }

    # ---- Find the header row ----
    header_index = None
    roll_index = None
    name_index = None

    # Look for a header row among the first few rows
    max_scan = min(len(rows), 6)

    for i in range(max_scan):

        cells = [
            _normalize_cell(c) for c in rows[i]
        ]

        r, n = _detect_columns(cells)

        if r is not None and n is not None and r != n:

            header_index = i
            roll_index = r
            name_index = n
            break

    data_start = 0

    if header_index is not None:

        data_start = header_index + 1

    else:

        # No header: assume first two columns
        roll_index = 0
        name_index = 1

    students = []
    seen_rolls = set()
    duplicates = []
    errors = []
    empty_rows = 0

    for row in rows[data_start:]:

        cells = [
            _normalize_cell(c) for c in row
        ]

        roll_text = (
            cells[roll_index]
            if roll_index < len(cells) else ""
        )

        name_text = (
            cells[name_index]
            if name_index < len(cells) else ""
        )

        name_clean = _clean_name(name_text)

        # Skip completely empty rows
        if roll_text.strip() == "" and name_clean == "":

            empty_rows += 1
            continue

        # Skip trailing header-ish rows like 'Notes' etc.
        if name_clean.lower() in ("name", "student", "student name"):
            empty_rows += 1
            continue

        roll_value = _valid_roll(roll_text)

        if roll_value is None:

            errors.append(
                "Row missing a valid roll number: '" +
                roll_text + "' (name: " + (name_clean or "?") + ")"
            )
            continue

        if name_clean == "":

            errors.append(
                "Row missing a student name (roll " +
                str(roll_value) + ")"
            )
            continue

        if roll_value in seen_rolls:

            duplicates.append({
                "roll": roll_value,
                "name": name_clean
            })
            continue

        seen_rolls.add(roll_value)

        students.append({
            "roll": roll_value,
            "name": name_clean
        })

    if not students and not errors and not duplicates:

        return {
            "success": False,
            "error": "No student data could be read from the file.",
            "students": [],
            "message": "",
            "duplicates": [],
            "empty_rows": empty_rows,
            "errors": []
        }

    # Order by roll number
    students.sort(key=lambda s: s["roll"])

    return {
        "success": True,
        "error": None,
        "students": students,
        "message": "Imported " + str(len(students)) + " students.",
        "duplicates": duplicates,
        "empty_rows": empty_rows,
        "errors": errors
    }

