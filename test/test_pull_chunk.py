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


def _bare_inlet(channel_count=1):
    """A StreamInlet with no liblsl object, for exercising pure-Python logic."""
    inlet = object.__new__(pylsl.StreamInlet)
    inlet.as_numpy = False
    inlet.np_dtype = np.float32
    inlet.value_type = ctypes.c_float
    inlet.channel_count = channel_count
    return inlet


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
    inlet = _bare_inlet()
    calls = []
    responses = [
        ([[1.0], [2.0]], [1.0, 2.0]),
        ([[3.0], [4.0]], [3.0, 4.0]),
    ]

    def pull_once(timeout, max_samples, dest_obj, as_numpy=False):
        calls.append((timeout, max_samples, dest_obj))
        return responses.pop(0)

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    samples, timestamps = inlet.pull_chunk(timeout=0.5, max_samples=5, min_samples=2)

    assert samples == [[1.0], [2.0], [3.0], [4.0]]
    assert timestamps == [1.0, 2.0, 3.0, 4.0]
    assert calls == [(0.5, 2, None), (0.0, 3, None)]


def test_pull_chunk_min_samples_timeout_does_not_drain(monkeypatch):
    inlet = _bare_inlet()
    calls = []

    def pull_once(timeout, max_samples, dest_obj, as_numpy=False):
        calls.append((timeout, max_samples, dest_obj))
        return [], []

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    samples, timestamps = inlet.pull_chunk(timeout=0.5, max_samples=5, min_samples=1)

    assert samples == []
    assert timestamps == []
    assert calls == [(0.5, 1, None)]


def test_pull_chunk_min_samples_appends_into_dest_obj(monkeypatch):
    inlet = _bare_inlet()
    inlet.value_type = ctypes.c_float
    inlet.channel_count = 2
    calls = []

    def pull_once(timeout, max_samples, dest_obj, as_numpy=False):
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
    inlet = _bare_inlet()

    with pytest.raises(ValueError, match="between 1 and max_samples"):
        inlet.pull_chunk(max_samples=4, min_samples=min_samples)


def test_pull_chunk_default_retains_single_call(monkeypatch):
    inlet = _bare_inlet()
    calls = []

    def pull_once(timeout, max_samples, dest_obj, as_numpy=False):
        calls.append((timeout, max_samples, dest_obj))
        return [[1.0]], [1.0]

    monkeypatch.setattr(inlet, "_pull_chunk_once", pull_once)

    result = inlet.pull_chunk(timeout=0.25, max_samples=7)

    assert result == ([[1.0]], [1.0])
    assert calls == [(0.25, 7, None)]


def _open_pair(source_id, channel_count, channel_format, **inlet_kw):
    info = pylsl.StreamInfo(
        name=source_id,
        type="test",
        channel_count=channel_count,
        nominal_srate=0,
        channel_format=channel_format,
        source_id=source_id,
    )
    outlet = pylsl.StreamOutlet(info)
    streams = pylsl.resolve_byprop("source_id", source_id, timeout=2)
    assert streams, "outlet was not discovered"
    inlet = pylsl.StreamInlet(streams[0], **inlet_kw)
    inlet.open_stream(timeout=2)
    time.sleep(0.5)
    return outlet, inlet


def _collect(inlet, n_samples, **pull_kw):
    chunks, stamps = [], []
    got = 0
    deadline = time.time() + 5
    while got < n_samples and time.time() < deadline:
        c, t = inlet.pull_chunk(timeout=1.0, **pull_kw)
        if len(t):
            chunks.append(c)
            stamps.append(t)
            got += len(t)
    return chunks, stamps


def test_pull_chunk_as_numpy_returns_arrays_in_stream_dtype():
    data = np.arange(12, dtype=np.float64).reshape(4, 3) * 0.5
    outlet, inlet = _open_pair("test_as_numpy_id", 3, pylsl.cf_float32)
    outlet.push_chunk(data)
    chunks, stamps = _collect(inlet, 4, as_numpy=True)

    assert all(isinstance(c, np.ndarray) for c in chunks)
    assert all(isinstance(t, np.ndarray) for t in stamps)
    got = np.concatenate(chunks)
    assert got.dtype == np.float32
    assert got.shape == (4, 3)
    np.testing.assert_array_equal(got, data.astype(np.float32))
    ts = np.concatenate(stamps)
    assert ts.dtype == np.float64 and ts.shape == (4,)
    assert np.all(np.diff(ts) >= 0)


def test_inlet_as_numpy_default_applies_and_can_be_overridden():
    data = [[1.0, 2.0], [3.0, 4.0]]
    outlet, inlet = _open_pair(
        "test_as_numpy_default_id", 2, pylsl.cf_double64, as_numpy=True
    )
    outlet.push_chunk(data)
    chunks, stamps = _collect(inlet, 2)
    assert all(isinstance(c, np.ndarray) for c in chunks)
    np.testing.assert_array_equal(np.concatenate(chunks), np.array(data))

    outlet.push_chunk(data)
    chunks, stamps = _collect(inlet, 2, as_numpy=False)
    assert all(isinstance(c, list) for c in chunks)
    assert all(isinstance(t, list) for t in stamps)
    assert [row for c in chunks for row in c] == data


def test_pull_chunk_as_numpy_ignored_for_string_streams():
    data = [["a", "b"], ["c", "d"]]
    outlet, inlet = _open_pair("test_as_numpy_string_id", 2, pylsl.cf_string)
    outlet.push_chunk(data)
    chunks, stamps = _collect(inlet, 2, as_numpy=True)
    assert all(isinstance(c, list) for c in chunks)
    assert [row for c in chunks for row in c] == data


def test_pull_chunk_as_numpy_result_survives_next_pull():
    outlet, inlet = _open_pair("test_as_numpy_alias_id", 1, pylsl.cf_float32)
    outlet.push_chunk([[1.0], [2.0]])
    first, _ = _collect(inlet, 2, as_numpy=True)
    first = np.concatenate(first)
    snapshot = first.copy()
    outlet.push_chunk([[9.0], [9.0]])
    _collect(inlet, 2, as_numpy=True)
    np.testing.assert_array_equal(first, snapshot)


def test_pull_chunk_min_samples_concatenates_numpy_results():
    inlet = _bare_inlet()
    responses = [
        (np.array([[1.0], [2.0]], np.float32), np.array([1.0, 2.0])),
        (np.array([[3.0]], np.float32), np.array([3.0])),
    ]

    def pull_once(timeout, max_samples, dest_obj, as_numpy=False):
        assert as_numpy is True
        return responses.pop(0)

    inlet._pull_chunk_once = pull_once
    samples, ts = inlet.pull_chunk(
        timeout=0.5, max_samples=5, min_samples=2, as_numpy=True
    )
    np.testing.assert_array_equal(samples, [[1.0], [2.0], [3.0]])
    np.testing.assert_array_equal(ts, [1.0, 2.0, 3.0])


@pytest.mark.parametrize(
    "payload",
    [
        np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),  # wrong dtype
        np.asfortranarray(np.array([[1.0, 2.0], [3.0, 4.0]], np.float32)),  # F order
        [[1.0, 2.0], [3.0, 4.0]],  # nested list
        [1.0, 2.0, 3.0, 4.0],  # flat multiplexed list
        np.array([[1.0, 2.0], [3.0, 4.0]], np.float32)[:, ::1],  # fine view
    ],
    ids=["float64", "fortran", "nested", "flat", "view"],
)
def test_push_chunk_numeric_inputs_are_converted(payload):
    source_id = "test_push_conv_" + str(abs(hash(str(payload))) % 10**6)
    outlet, inlet = _open_pair(source_id, 2, pylsl.cf_float32)
    outlet.push_chunk(payload)
    chunks, _ = _collect(inlet, 2, as_numpy=True)
    np.testing.assert_array_equal(
        np.concatenate(chunks), np.array([[1.0, 2.0], [3.0, 4.0]], np.float32)
    )


def test_push_chunk_rejects_wrong_channel_count():
    outlet = pylsl.StreamOutlet(
        pylsl.StreamInfo("test_push_bad", "test", 2, 0, pylsl.cf_float32, "tpb")
    )
    with pytest.raises(ValueError):
        outlet.push_chunk([[1.0, 2.0, 3.0]])
    with pytest.raises(ValueError):
        outlet.push_chunk([1.0, 2.0, 3.0])
    outlet.push_chunk([])  # empty is a no-op, not an error
