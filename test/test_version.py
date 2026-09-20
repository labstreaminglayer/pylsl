import warnings

import pytest

import pylsl
from pylsl import util


def test_min_liblsl_version_is_sane_int():
    assert isinstance(pylsl.MIN_LIBLSL_VERSION, int)
    # 1.16.0 at the time of writing; anything outside this range is a typo.
    assert 100 <= pylsl.MIN_LIBLSL_VERSION <= 200


def test_installed_liblsl_meets_minimum():
    assert pylsl.library_version() >= pylsl.MIN_LIBLSL_VERSION


def test_no_warning_for_current_liblsl():
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert util._check_liblsl_version() is True


def test_warns_when_liblsl_too_old():
    too_old = pylsl.MIN_LIBLSL_VERSION - 1
    with pytest.warns(RuntimeWarning, match="pylsl requires at least"):
        assert util._check_liblsl_version(too_old) is False


def test_warns_when_lib_reports_old_version(monkeypatch):
    monkeypatch.setattr(
        util.lib, "lsl_library_version", lambda: pylsl.MIN_LIBLSL_VERSION - 1
    )
    with pytest.warns(RuntimeWarning):
        assert util._check_liblsl_version() is False
