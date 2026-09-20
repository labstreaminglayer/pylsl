"""Round-trip test for StreamInlet.pull_chunk.

Pushes a known chunk and pulls it back, asserting the extracted data is
identical in value, shape, and type. Covers both paths the bulk-slice
extraction must preserve: a multi-channel numeric chunk and a
variable-length string ("Markers"-style) chunk.
"""

import ctypes
import time

import numpy as np
import pytest

import pylsl

# (channel_format, samples) — distinct values per channel/sample, including
# empty and multi-byte strings to exercise variable-length decoding.
CASES = {
    "double64": (
        pylsl.cf_double64,
        [[1.0, 2.5, -3.25], [4.0, 5.5, 6.75], [7.0, 8.5, 9.25]],
    ),
    "string": (
        pylsl.cf_string,
        [["a", "bb", ""], ["ccc", "dddd", "e"], ["", "f", "ééé"]],
    ),
}


@pytest.mark.parametrize("channel_format,samples", CASES.values(), ids=CASES.keys())
def test_pull_chunk_roundtrip(channel_format: int, samples: list):
    n_samples = len(samples)
    n_channels = len(samples[0])

    info = pylsl.StreamInfo(
        name="test_pull_chunk",
        type="test",
        channel_count=n_channels,
        nominal_srate=0,
        channel_format=channel_format,
        source_id="test_pull_chunk_id",
    )
    outlet = pylsl.StreamOutlet(info)

    streams = pylsl.resolve_byprop("source_id", "test_pull_chunk_id", timeout=2)
    assert streams, "outlet was not discovered"
    inlet = pylsl.StreamInlet(streams[0])

    # Subscribe before pushing so the only chunk isn't sent before the inlet's
    # data connection is established.
    inlet.open_stream(timeout=2)
    time.sleep(0.5)
    outlet.push_chunk(samples)

    # Data may arrive in more than one chunk; collect until complete.
    got_samples: list = []
    got_ts: list = []
    deadline = time.time() + 5
    while len(got_samples) < n_samples and time.time() < deadline:
        chunk, stamps = inlet.pull_chunk(timeout=1.0)
        if chunk:
            assert isinstance(stamps, list)
            assert all(isinstance(row, list) for row in chunk)
        got_samples.extend(chunk)
        got_ts.extend(stamps)

    assert got_samples == samples
    assert len(got_ts) == n_samples


def test_pull_chunk_min_samples_returns_available_data_without_waiting_for_max():
    samples = [[1.0], [2.0], [3.0]]
    source_id = "test_pull_chunk_min_samples_id"
    info = pylsl.StreamInfo(
        name="test_pull_chunk_min_samples",
        type="test",
        channel_count=1,
        nominal_srate=0,
        channel_format=pylsl.cf_float32,
        source_id=source_id,
    )
    outlet = pylsl.StreamOutlet(info)
    streams = pylsl.resolve_byprop("source_id", source_id, timeout=2)
    assert streams, "outlet was not discovered"
    inlet = pylsl.StreamInlet(streams[0])
    inlet.open_stream(timeout=2)
    time.sleep(0.5)
    outlet.push_chunk(samples)

    deadline = time.monotonic() + 2
    while inlet.samples_available() < len(samples) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert inlet.samples_available() >= len(samples)

    started = time.monotonic()
    got_samples, timestamps = inlet.pull_chunk(
        timeout=1.0, max_samples=16, min_samples=1
    )
    elapsed = time.monotonic() - started

    assert got_samples == samples
    assert len(timestamps) == len(samples)
    assert elapsed < 0.5


def test_pull_chunk_min_samples_drains_without_blocking(monkeypatch):
    inlet = object.__new__(pylsl.StreamInlet)
    calls = []
    responses = [
        ([[1.0], [2.0]], [1.0, 2.0]),
        ([[3.0], [4.0]], [3.0, 4.0]),
    ]

    def pull_once(timeout, max_samples, dest_obj):
        calls.append((timeout, max_samples, dest_obj))
        return responses.pop(0)

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    samples, timestamps = inlet.pull_chunk(timeout=0.5, max_samples=5, min_samples=2)

    assert samples == [[1.0], [2.0], [3.0], [4.0]]
    assert timestamps == [1.0, 2.0, 3.0, 4.0]
    assert calls == [(0.5, 2, None), (0.0, 3, None)]


def test_pull_chunk_min_samples_timeout_does_not_drain(monkeypatch):
    inlet = object.__new__(pylsl.StreamInlet)
    calls = []

    def pull_once(timeout, max_samples, dest_obj):
        calls.append((timeout, max_samples, dest_obj))
        return [], []

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    samples, timestamps = inlet.pull_chunk(timeout=0.5, max_samples=5, min_samples=1)

    assert samples == []
    assert timestamps == []
    assert calls == [(0.5, 1, None)]


def test_pull_chunk_min_samples_appends_into_dest_obj(monkeypatch):
    inlet = object.__new__(pylsl.StreamInlet)
    inlet.value_type = ctypes.c_float
    inlet.channel_count = 2
    calls = []

    def pull_once(timeout, max_samples, dest_obj):
        calls.append((timeout, max_samples, dest_obj))
        view = np.frombuffer(dest_obj, dtype=np.float32).reshape(-1, 2)
        if timeout:
            view[0] = [1.0, 2.0]
            return None, [1.0]
        view[:2] = [[3.0, 4.0], [5.0, 6.0]]
        return None, [2.0, 3.0]

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)
    dest = np.zeros((4, 2), dtype=np.float32)

    samples, timestamps = inlet.pull_chunk(
        timeout=0.5,
        max_samples=len(dest),
        dest_obj=dest,
        min_samples=1,
    )

    assert samples is None
    assert timestamps == [1.0, 2.0, 3.0]
    np.testing.assert_array_equal(
        dest, [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [0.0, 0.0]]
    )
    assert calls[0][:2] == (0.5, 1)
    assert calls[0][2] is dest
    assert calls[1][:2] == (0.0, 3)
    assert isinstance(calls[1][2], memoryview)


@pytest.mark.parametrize("min_samples", [0, 5])
def test_pull_chunk_rejects_invalid_min_samples(min_samples):
    inlet = object.__new__(pylsl.StreamInlet)

    with pytest.raises(ValueError, match="between 1 and max_samples"):
        inlet.pull_chunk(max_samples=4, min_samples=min_samples)


def test_pull_chunk_default_retains_single_call(monkeypatch):
    inlet = object.__new__(pylsl.StreamInlet)
    calls = []

    def pull_once(timeout, max_samples, dest_obj):
        calls.append((timeout, max_samples, dest_obj))
        return [[1.0]], [1.0]

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    result = inlet.pull_chunk(timeout=0.25, max_samples=7)

    assert result == ([[1.0]], [1.0])
    assert calls == [(0.25, 7, None)]
