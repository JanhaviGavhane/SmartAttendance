

# ===== VOSK SPEECH TO TEXT SERVICE =====
#
# Local, offline speech recognition using Vosk.
# No API key, no internet, no paid service.
#
# Vosk requires a downloaded language model. The model used here
# is the small English model (vosk-model-small-en-us-0.15), stored
# in the /models folder of this project.
#
# Vosk expects raw PCM audio at 16 kHz, single channel.
# Browser audio (WebM/Opus) is decoded to PCM using PyAV before
# it is passed to Vosk.

import os
import re
import threading

# PyAV decodes browser audio into raw PCM samples
try:
    import av
    _AV_AVAILABLE = True
except Exception:  # pragma: no cover
    _AV_AVAILABLE = False

# Vosk
from vosk import Model, KaldiRecognizer, SetLogLevel


# ============================================================
# ===== MODEL LOCATION ========================================
# ============================================================

# Find the model folder inside this project.
_MODEL_NAME = "vosk-model-small-en-us-0.15"

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MODEL_PATH = os.path.join(
    _BASE_DIR,
    "models",
    _MODEL_NAME
)

if not os.path.isdir(_MODEL_PATH):

    # Fall back to any vosk model directory found in /models
    _models_root = os.path.join(_BASE_DIR, "models")

    if os.path.isdir(_models_root):

        for entry in os.listdir(_models_root):

            candidate = os.path.join(_models_root, entry)

            if os.path.isdir(candidate) and "am" in os.listdir(candidate):
                _MODEL_PATH = candidate
                break


# ============================================================
# ===== GLOBAL MODEL + LOCK ===================================
# ============================================================

# Vosk Model is expensive to load, so load it once and reuse it.
# A lock prevents two requests loading/using it at the same time.
_model = None
_model_lock = threading.Lock()


def _get_model():
    """Load the Vosk model once (thread-safe)."""

    global _model

    if _model is not None:
        return _model

    with _model_lock:

        if _model is not None:
            return _model

        if not os.path.isdir(_MODEL_PATH):

            raise RuntimeError(
                "Vosk model not found. Download the model "
                "and place it in the /models folder."
            )

        # Silence Vosk's internal logging
        SetLogLevel(-1)

        _model = Model(_MODEL_PATH)

    return _model


# ============================================================
# ===== DECODE AUDIO TO 16kHz MONO PCM ========================
# ============================================================

def _decode_to_pcm(filepath):
    """Decode any browser audio (webm/opus/wav) to mono 16 kHz
    PCM bytes so Vosk can process it.

    Returns: (pcm_bytes, sample_rate)
    """

    if not _AV_AVAILABLE:

        raise RuntimeError(
            "PyAV (av) is required to decode audio for Vosk."
        )

    pcm_chunks = []

    sample_rate = None

    with av.open(filepath) as container:

        # Find the first audio stream
        stream = None

        for s in container.streams:

            if s.type == "audio":
                stream = s
                break

        if stream is None:

            raise RuntimeError(
                "No audio stream found in the uploaded file."
            )

        sample_rate = stream.codec_context.sample_rate or 16000

        # Resample to mono 16 kHz if needed
        resampler = av.AudioResampler(
            format="s16",
            layout="mono",
            rate=16000
        )

        for frame in container.decode(stream):

            if frame.samples == 0:
                continue

            resampled = resampler.resample(frame)

            for out_frame in resampled:

                pcm_chunks.append(
                    bytes(out_frame.to_ndarray().tobytes())
                )

        # Flush the resampler
        for out_frame in resampler.resample(None):

            pcm_chunks.append(
                bytes(out_frame.to_ndarray().tobytes())
            )

    pcm = b"".join(pcm_chunks)

    return pcm, 16000


# ============================================================
# ===== TRANSCRIBE ============================================
# ============================================================

def transcribe_audio(filepath):
    """Recognize speech in an audio file and return the text."""

    model = _get_model()

    pcm, sample_rate = _decode_to_pcm(filepath)

    if not pcm:

        return ""

    recognizer = KaldiRecognizer(
        model,
        sample_rate
    )

    # Give Vosk the full audio at once.
    # AcceptResult returns the final recognized text.
    if recognizer.AcceptWaveform(pcm):

        result = recognizer.Result()

    else:

        result = recognizer.FinalResult()

    # Result looks like:
    #   {"text": "twenty one"}
    import json

    try:

        data = json.loads(result)

        text = (data.get("text") or "").strip()

    except Exception:

        text = ""

    return text


# ============================================================
# ===== MAP SPOKEN WORDS TO A ROLL NUMBER ====================
# ============================================================

_BASIC = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90
}

# Common speech-to-text spelling mistakes / variants
_FIXES = {
    "won": "one",
    "to": "two",
    "too": "two",
    "for": "four",
    "fore": "four",
    "ate": "eight",
    "for ty": "forty",
    "for ty one": "forty one",
    "thirti": "thirty",
    "forti": "forty",
    "twenti": "twenty",
    "fifty": "fifty",
    "ninty": "ninety",
    "fortyfive": "forty five",
    "twentyone": "twenty one",
    "thirtyfive": "thirty five",
    "fortyseven": "forty seven",
    "twenty five": "twenty five",
    "eh": "a",
    "ix": "six",
    "sex": "six",
    "tree": "three"
}


def extract_roll_number(text):
    """Convert recognized speech into ONE roll number.

    Returns an int (1-100) or None if not recognized.

    Deliberately does NOT join random separate digits together
    (e.g. "two three" is NOT turned into 23) to avoid the previous
    single-digit problem.
    """

    if not text:
        return None

    cleaned = text.lower().strip()
    cleaned = re.sub(r"[-–—]+", " ", cleaned)
    cleaned = re.sub(r"[.,!?'\"]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Remove filler words often captured around the number
    for filler in (
        r"\broll number\b",
        r"\bmy\b",
        r"\bi am\b",
        r"\bi\b",
        r"\bam\b",
        r"\bim\b",
        r"\broll\b",
        r"\bnumber\b",
        r"\bsir\b",
        r"\bma'am\b",
        r"\bmam\b",
        r"\bpresent\b",
        r"\bye\b",
        r"\boh\b",
        r"\bkeep\b",
    ):
        cleaned = re.sub(filler, " ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # ---- Direct digit ----
    # "1" -> 1, "21" -> 21, "35" -> 35
    m = re.fullmatch(r"(\d{1,3})", cleaned)

    if m:

        value = int(m.group(1))

        if 1 <= value <= 100:

            return value

    m = re.search(r"(?<!\d)(\d{1,3})(?!\d)", cleaned)

    if m:

        value = int(m.group(1))

        if 1 <= value <= 100:

            return value

    # ---- Apply common spelling fixes ----
    words = cleaned.split(" ")

    fixed_words = []

    for word in words:

        fixed_words.append(_FIXES.get(word, word))

    fixed = " ".join(fixed_words)

    # ---- Exact basic number ----
    # "one" -> 1 ... "nineteen" -> 19
    if fixed in _BASIC:

        return _BASIC[fixed]

    # ---- Exact tens ----
    # "twenty" -> 20
    if fixed in _TENS:

        return _TENS[fixed]

    # ---- 100 ----
    if fixed in ("one hundred", "hundred"):

        return 100

    # ---- "twenty one" style (tens + unit) ----
    parts = fixed.split(" ")

    if len(parts) == 2:

        first, second = parts

        if (
            first in _TENS and
            second in _BASIC and
            _BASIC[second] >= 1 and
            _BASIC[second] <= 9
        ):

            return _TENS[first] + _BASIC[second]

    # ---- Compressed forms like "twentyone", "fortyseven" ----
    # Only merge if the whole string is exactly a tens+unit combo.
    for ten_word, ten_value in _TENS.items():

        if fixed == ten_word:

            return ten_value

        if fixed.startswith(ten_word):

            unit_text = fixed[len(ten_word):]

            if unit_text in _BASIC and 1 <= _BASIC[unit_text] <= 9:

                return ten_value + _BASIC[unit_text]

    # ---- Single digit captured as a word inside a longer phrase ----
    # e.g. Vosk sometimes returns "for two" or "two sir".
    # Only accept a lone basic word when it is the ONLY number word.
    if fixed in _BASIC:

        return _BASIC[fixed]

    return None

