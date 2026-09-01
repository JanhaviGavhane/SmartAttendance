"""TEST 13 - Proxy removal: no proxy functionality anywhere.

Normal Vosk roll-number recognition must still work.
"""

import os
import glob

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUFFIXES = (".py", ".js", ".html")
FORBIDDEN = [
    "proxy",
    "Proxy",
    "speaker_service",
    "voice_profile",
    "voice/status",
    "voice/enroll",
    "voice/verify",
    "resemblyzer",
    "get_enrolled_rolls",
    "save_voice_profile",
    "has_voice_profile",
]


def _project_files():
    for suffix in SUFFIXES:
        for path in glob.glob(os.path.join(PROJECT_ROOT, "**", "*" + suffix),
                              recursive=True):
            rel = os.path.relpath(path, PROJECT_ROOT)
            if (os.sep + "venv" + os.sep) in os.sep + rel + os.sep:
                continue
            if (os.sep + "tests" + os.sep) in os.sep + rel + os.sep:
                continue
            yield rel, path


def test_no_proxy_service_file():
    assert not os.path.exists(
        os.path.join(PROJECT_ROOT, "services", "speaker_service.py")
    )


def test_no_proxy_routes():
    import app as appmod
    paths = {r.rule for r in appmod.app.url_map.iter_rules()}
    assert "/voice/status" not in paths
    assert "/voice/enroll" not in paths
    assert "/voice/verify" not in paths


def test_no_proxy_references_in_source():
    offenders = []
    for rel, path in _project_files():
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        for keyword in FORBIDDEN:
            if keyword in content:
                offenders.append((rel, keyword))
    assert not offenders, f"Proxy references found: {offenders}"


def test_no_voice_profiles_table():
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