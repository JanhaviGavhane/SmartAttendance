"""TEST 9 - Vosk transcription endpoint (existing, not rewritten).

Uses generated audio if the environment supports it; otherwise skipped
gracefully so the suite still completes on machines without audio
tooling. The Vosk endpoint itself is NOT modified by tests.
"""

import pytest
import os
import io


def _make_audio_bytes() -> bytes:
    """Create a small valid WAV (1 s of near-silence) for the /transcribe
    endpoint using only the standard library."""
    import struct
    rate = 16000
    n_samples = rate  # 1 second
    data = bytearray()
    for i in range(n_samples):
        # Near-silence sine at low amplitude
        import math
        val = int(800 * math.sin(2 * math.pi * 440 * i / rate))
        data += struct.pack("<h", val)
    header = io.BytesIO()
    header.write(b"RIFF")
    header.write(struct.pack("<I", 36 + len(data)))
    header.write(b"WAVE")
    header.write(b"fmt ")
    header.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
    header.write(b"data")
    header.write(struct.pack("<I", len(data)))
    return header.getvalue() + bytes(data)


def test_transcribe_requires_auth(client):
    resp = client.post(
        "/transcribe",
        data={"audio": (io.BytesIO(b"\x00" * 100), "sample.wav")},
        content_type="multipart/form-data",
    )
    # Unauthenticated multipart requests hit the login redirect (302);
    # JSON requests get 401. Either means "not accessible anonymously".
    assert resp.status_code in (302, 401)


def test_transcribe_missing_audio_errors(client):
    from tests.conftest import register
    register(client, "voice_teacher")
    resp = client.post(
        "/transcribe",
        data={},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_transcribe_invalid_audio_errors(client):
    from tests.conftest import register
    register(client, "voice_teacher2")
    resp = client.post(
        "/transcribe",
        data={"audio": (io.BytesIO(b"not audio at all"), "bad.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (400, 500)


@pytest.mark.skipif(
    os.environ.get("DISABLE_VOSK_AUDIO_TESTS") == "1",
    reason="Real-audio Vosk test disabled by env; model may be unavailable.",
)
def test_transcribe_valid_wav(client):
    from tests.conftest import register
    register(client, "voice_teacher3")
    resp = client.post(
        "/transcribe",
        data={"audio": (io.BytesIO(_make_audio_bytes()), "tone.wav")},
        content_type="multipart/form-data",
    )
    # Endpoint must respond (2xx) with JSON; transcription may be empty
    # for silence but must not 500 on a well-formed WAV.
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)