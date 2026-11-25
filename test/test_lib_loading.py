import ctypes
import ctypes.util
import platform
import runpy
from pathlib import Path
from shutil import copyfile
from unittest.mock import Mock

import pytest


def test_linux_load_error_suggests_library_paths(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[1] / "src/pylsl/lib/__init__.py"
    loader = tmp_path / "loader.py"
    copyfile(source, loader)
    monkeypatch.delenv("PYLSL_LIB", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(ctypes.util, "find_library", lambda name: "liblsl.so.2")
    load_library = Mock(side_effect=OSError("cannot open shared object file"))
    monkeypatch.setattr(ctypes, "CDLL", load_library)

    with pytest.raises(RuntimeError, match="found but could not be loaded") as error:
        runpy.run_path(str(loader))

    load_library.assert_called_once_with("liblsl.so.2")
    assert "PYLSL_LIB" in str(error.value)
    assert "LD_LIBRARY_PATH" in str(error.value)
