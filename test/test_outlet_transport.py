"""Tests for StreamOutlet transport_flags, including synchronous (zero-copy) mode.

Synchronous mode requires liblsl >= 1.18.0 (the transp_sync_blocking transport
flag). Tests that exercise it are skipped on older libraries.
"""

import time

import pytest

import pylsl

_has_sync = pylsl.library_version() >= 118


def test_transport_constants_exposed():
    assert pylsl.transp_default == 0
    assert pylsl.transp_bufsize_samples == 1
    assert pylsl.transp_bufsize_thousandths == 2
    assert pylsl.transp_sync_blocking == 4


def test_default_outlet_still_works():
    """transport_flags defaults to 0 (async); the standard path is unchanged."""
    info = pylsl.StreamInfo("TA", "EEG", 4, 100, pylsl.cf_float32, source_id="ta")
    outlet = pylsl.StreamOutlet(info)
    assert outlet.get_info().name() == "TA"


@pytest.mark.skipif(
    not _has_sync, reason="requires liblsl >= 1.18.0 (transp_sync_blocking)"
)
def test_sync_outlet_round_trip():
    info = pylsl.StreamInfo("TS", "EEG", 4, 100, pylsl.cf_float32, source_id="ts")
    outlet = pylsl.StreamOutlet(info, transport_flags=pylsl.transp_sync_blocking)

    streams = pylsl.resolve_byprop("name", "TS", timeout=10.0)
    assert streams, "outlet was not resolved"
    inlet = pylsl.StreamInlet(streams[0])
    inlet.open_stream(timeout=10.0)
    time.sleep(0.5)  # let the sync socket handoff complete before pushing

    sent = [[float(i)] * 4 for i in range(5)]
    for sample in sent:
        outlet.push_sample(sample)

    received = []
    for _ in range(len(sent)):
        sample, _ts = inlet.pull_sample(timeout=5.0)
        if sample is None:
            break
        received.append(sample)

    assert received == sent
