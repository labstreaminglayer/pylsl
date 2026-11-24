"""time_correction / time_correction_ex against a local outlet."""

import pylsl


def test_time_correction_ex():
    info = pylsl.StreamInfo("test_tc_ex", "test", 1, 100, pylsl.cf_float32, "tc_ex_uid")
    outlet = pylsl.StreamOutlet(info)
    (match,) = pylsl.resolve_byprop("source_id", "tc_ex_uid", timeout=5)
    inlet = pylsl.StreamInlet(match)
    correction, remote_time, uncertainty = inlet.time_correction_ex(timeout=5)
    # Same machine: offset ~0, remote clock ~ our clock, a finite positive error bound.
    assert abs(correction) < 0.01
    assert abs(remote_time - pylsl.local_clock()) < 5
    assert 0 <= uncertainty < 1
    assert abs(inlet.time_correction(timeout=5) - correction) < 0.01
    del inlet, outlet
