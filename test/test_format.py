import ctypes

import pytest

import pylsl


@pytest.mark.parametrize(
    "channel_format", [pylsl.cf_int32, pylsl.cf_float32, pylsl.cf_double64]
)
def test_format(channel_format: int):
    expected_type = {
        pylsl.cf_int32: ctypes.c_int,
        pylsl.cf_float32: ctypes.c_float,
        pylsl.cf_double64: ctypes.c_double,
    }[channel_format]

    feature_info = pylsl.StreamInfo(
        name="test",
        type="EEG",
        channel_count=1,
        nominal_srate=1,
        channel_format=channel_format,
        source_id="testid",
    )
    outlet = pylsl.StreamOutlet(feature_info)
    assert outlet.value_type == expected_type

    streams = pylsl.resolve_byprop("name", "test", timeout=1)
    inlet = pylsl.StreamInlet(streams[0])

    assert inlet.value_type == expected_type
