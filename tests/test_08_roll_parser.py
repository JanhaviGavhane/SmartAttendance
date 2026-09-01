"""TEST 8 - Roll-number recognition parser (pure function, no audio)."""

from services.vosk_service import extract_roll_number

CASES = [
    ("one", 1),
    ("five", 5),
    ("ten", 10),
    ("twenty one", 21),
    ("twenty three", 23),
    ("one hundred", 100),
    ("100", 100),
    ("1", 1),
    ("35", 35),
    ("roll number seven", 7),
    ("twenty", 20),
]


def test_valid_rolls():
    for text, expected in CASES:
        assert extract_roll_number(text) == expected, f"{text} -> {expected}"


def test_invalid_rolls():
    for text in ("two three", "101", "200", "one hundred one", ""):
        assert extract_roll_number(text) is None, f"{text} should be None"


def test_does_not_join_random_digits():
    assert extract_roll_number("two three") is None
    assert extract_roll_number("four five six") is None