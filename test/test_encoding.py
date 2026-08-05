"""Tests for metadata strings that are not valid UTF-8.

Windows reports the hostname in the active ANSI code page, so a machine whose
name contains accented characters hands liblsl bytes that a strict UTF-8 decode
rejects. See https://github.com/labstreaminglayer/pylsl/issues/69.
"""

import pylsl
from pylsl.util import _to_str

# "PC-Ferná" in cp1252/latin-1. The trailing 0xe1 is not valid UTF-8.
NON_UTF8_BYTES = b"PC-Fern\xe1"
NON_UTF8_TEXT = "PC-Ferná"


def new_info():
    return pylsl.StreamInfo(
        name="TestNonUTF8", type="Markers", channel_count=1, source_id="test_non_utf8"
    )


def test_to_str_prefers_utf8():
    # "hostname-é" as UTF-8, which must not be reinterpreted as latin-1.
    assert _to_str(b"hostname-\xc3\xa9") == "hostname-é"


def test_to_str_falls_back_on_non_utf8():
    assert _to_str(NON_UTF8_BYTES) == NON_UTF8_TEXT


def test_to_str_fallback_preserves_bytes():
    assert _to_str(NON_UTF8_BYTES).encode("latin-1") == NON_UTF8_BYTES


def test_hostname_with_non_utf8_bytes(monkeypatch):
    info = new_info()
    monkeypatch.setattr(pylsl.info.lib, "lsl_get_hostname", lambda obj: NON_UTF8_BYTES)
    assert info.hostname() == NON_UTF8_TEXT


def test_as_xml_with_non_utf8_bytes(monkeypatch):
    info = new_info()
    xml = b"<info><hostname>" + NON_UTF8_BYTES + b"</hostname></info>"
    monkeypatch.setattr(pylsl.info.lib, "lsl_get_xml", lambda obj: xml)
    assert NON_UTF8_TEXT in info.as_xml()


def test_child_value_with_non_utf8_bytes(monkeypatch):
    info = new_info()
    info.desc().append_child_value("manufacturer", "pytest")
    monkeypatch.setattr(
        pylsl.info.lib, "lsl_child_value_n", lambda elem, name: NON_UTF8_BYTES
    )
    assert info.desc().child_value("manufacturer") == NON_UTF8_TEXT
