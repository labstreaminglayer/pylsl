"""Tests for set_config_filename and set_config_content.

Both functions must run before liblsl's config is loaded (on first use), so
the effect-verifying tests run in a fresh Python subprocess. In-process smoke
tests only verify that the call path works — they may be no-ops if liblsl has
already initialized in the current process.
"""

import subprocess
import sys
import textwrap

import pytest

import pylsl


def test_set_config_content_accepts_string():
    # Safe to call even after init — content is simply ignored once liblsl has loaded.
    pylsl.set_config_content("[lab]\nSessionID = ignored_after_init\n")


def test_set_config_filename_accepts_string():
    pylsl.set_config_filename("/nonexistent/path/to/lsl.cfg")


def test_set_config_content_rejects_non_string():
    with pytest.raises(AttributeError):
        pylsl.set_config_content(b"not a str")


def test_set_config_filename_rejects_non_string():
    with pytest.raises(AttributeError):
        pylsl.set_config_filename(12345)


def _run_in_subprocess(script: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_set_config_content_applies_session_id():
    """Setting content before any LSL call should update the session id that
    outlets inherit from the library config."""
    session_id = "pytest_content_session"
    script = textwrap.dedent(f"""
        import pylsl
        pylsl.set_config_content('[lab]\\nSessionID = {session_id}\\n')
        info = pylsl.StreamInfo('T', 'EEG', 1, 100, 'float32', 'src')
        outlet = pylsl.StreamOutlet(info)
        print(outlet.get_info().session_id())
    """)
    assert _run_in_subprocess(script) == session_id


def test_set_config_filename_applies_session_id(tmp_path):
    session_id = "pytest_filename_session"
    cfg = tmp_path / "lsl.cfg"
    cfg.write_text(f"[lab]\nSessionID = {session_id}\n")
    script = textwrap.dedent(f"""
        import pylsl
        pylsl.set_config_filename({str(cfg)!r})
        info = pylsl.StreamInfo('T', 'EEG', 1, 100, 'float32', 'src')
        outlet = pylsl.StreamOutlet(info)
        print(outlet.get_info().session_id())
    """)
    assert _run_in_subprocess(script) == session_id
