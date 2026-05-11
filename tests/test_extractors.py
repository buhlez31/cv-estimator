"""Unit tests for extractors/document.py (text + language detection)."""

import pytest

from cv_estimator.extractors import document


def test_detect_czech_via_diacritics():
    text = "Vystudoval jsem strojírenství na ČVUT. Pracoval jsem jako vedoucí týmu."
    assert document.detect_language(text) == "cs"


def test_detect_english():
    text = "I am a software engineer with 5 years of experience in Python and AWS."
    assert document.detect_language(text) == "en"


def test_detect_czech_via_stopwords_without_diacritics():
    text = "Pracoval jsem v firme jako analytik a vedl jsem tym lidi."
    assert document.detect_language(text) == "cs"


def test_extract_text_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file extension"):
        document.extract_text(b"x", "cv.docs")


def test_extract_text_txt():
    raw = b"Hello world.\nLine 2."
    out = document.extract_text(raw, "sample.txt")
    assert "Hello world" in out
    assert "Line 2" in out


def test_normalize_collapses_whitespace():
    raw = b"a\r\n\r\n\r\n\r\nb     c"
    out = document.extract_text(raw, "x.txt")
    assert out == "a\n\nb c"
