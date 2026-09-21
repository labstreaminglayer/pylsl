"""String streams carry length-delimited blobs. Outlets accept str or bytes-like
values; inlets return decoded str by default or raw bytes with as_numpy=True.
See issue #54."""

import time
import uuid

import numpy as np
import pytest

import pylsl

# Payloads that break C-string handling: embedded NULs, invalid UTF-8, empty.
BLOBS = [
    [b"\x00\x01\x02", b"plain"],
    [b"", b"\xff\xfe\xfd\x00\x00tail"],
    [bytes(range(256)), b"\x00"],
]


def _pair(channel_count=2, **inlet_kw):
    sid = "blob_" + uuid.uuid4().hex[:8]
    info = pylsl.StreamInfo(sid, "Blob", channel_count, 0, pylsl.cf_string, sid)
    outlet = pylsl.StreamOutlet(info)
    found = pylsl.resolve_byprop("source_id", sid, timeout=5)
    assert found
    inlet = pylsl.StreamInlet(found[0], **inlet_kw)
    inlet.open_stream(timeout=5)
    time.sleep(0.3)
    return outlet, inlet


def _one(inlet, **kw):
    deadline = time.time() + 5
    sample, ts = None, None
    while ts is None and time.time() < deadline:
        sample, ts = inlet.pull_sample(timeout=1.0, **kw)
    assert ts is not None
    return sample


def _collect(inlet, n, **kw):
    out, ts = [], []
    deadline = time.time() + 5
    while len(out) < n and time.time() < deadline:
        c, t = inlet.pull_chunk(timeout=1.0, **kw)
        out.extend(c)
        ts.extend(t)
    return out, ts


@pytest.mark.parametrize("blob", BLOBS, ids=["nul", "nonutf8", "allbytes"])
def test_sample_roundtrip_as_numpy_returns_raw_bytes(blob):
    outlet, inlet = _pair(as_numpy=True)
    outlet.push_sample(blob)
    sample = _one(inlet)
    assert isinstance(sample, np.ndarray) and sample.dtype == object
    assert sample.tolist() == blob


def test_sample_default_decodes_and_preserves_nul():
    outlet, inlet = _pair()
    outlet.push_sample(["ab\x00cd", "é"])
    assert _one(inlet) == ["ab\x00cd", "é"]
    outlet.push_sample([b"ab\x00cd", b"\xc3\xa9"])  # bytes in, str out
    assert _one(inlet) == ["ab\x00cd", "é"]


def test_push_sample_accepts_bytearray_and_memoryview():
    outlet, inlet = _pair(as_numpy=True)
    outlet.push_sample([bytearray(b"\x00ab"), memoryview(b"cd\x00")])
    assert _one(inlet).tolist() == [b"\x00ab", b"cd\x00"]


def test_chunk_roundtrip_nested_and_flat():
    outlet, inlet = _pair()
    outlet.push_chunk(BLOBS)
    got, ts = _collect(inlet, len(BLOBS), as_numpy=True)
    assert [list(r) for r in got] == BLOBS
    assert len(ts) == len(BLOBS)
    outlet.push_chunk([v for row in BLOBS for v in row])
    got, _ = _collect(inlet, len(BLOBS), as_numpy=True)
    assert [list(r) for r in got] == BLOBS


def test_chunk_mixed_str_and_bytes_with_per_sample_timestamps():
    outlet, inlet = _pair(as_numpy=True)
    rows = [["text", b"\x00\x00"], [b"", "é"], ["\x00", b"\xff"]]
    stamps = [1000.0, 1001.0, 1002.0]
    outlet.push_chunk(rows, timestamp=stamps)
    got, ts = _collect(inlet, len(rows))
    assert [list(r) for r in got] == [
        [b"text", b"\x00\x00"],
        [b"", b"\xc3\xa9"],
        [b"\x00", b"\xff"],
    ]
    assert np.allclose(np.diff(ts), np.diff(stamps), atol=1e-3)


def test_per_call_as_numpy_overrides_inlet_default():
    outlet, inlet = _pair(as_numpy=True)
    outlet.push_chunk([["x", "y"]])
    got, ts = _collect(inlet, 1, as_numpy=False)
    assert got == [["x", "y"]] and isinstance(ts, list)


def test_non_utf8_bytes_with_default_decoding_raises():
    outlet, inlet = _pair()
    outlet.push_sample([b"\xff", b"ok"])
    with pytest.raises(UnicodeDecodeError):
        _one(inlet)


def test_string_pull_frees_every_slot(monkeypatch):
    freed = []
    monkeypatch.setattr(pylsl.inlet, "_destroy_string_array", None)
    monkeypatch.setattr(pylsl.inlet.lib, "lsl_destroy_string", freed.append)
    outlet, inlet = _pair()
    outlet.push_sample(["\x00", "\x00\x00"])
    _one(inlet)
    assert len(freed) == 2 and all(freed)
    freed.clear()
    outlet.push_chunk(BLOBS)
    _collect(inlet, len(BLOBS), max_samples=4, as_numpy=True)
    assert freed and len(freed) % 2 == 0
