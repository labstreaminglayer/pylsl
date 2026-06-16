"""Round-trip test for StreamInlet.pull_chunk.

Pushes a known chunk and pulls it back, asserting the extracted data is
identical in value, shape, and type. Covers both paths the bulk-slice
extraction must preserve: a multi-channel numeric chunk and a
variable-length string ("Markers"-style) chunk.
"""

import time

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
