import pytest

import pylsl

_has_reset_uid = hasattr(pylsl.info.lib, "lsl_reset_uid")


def test_info_src_id():
    name = "TestName"
    strm_type = "TestType"
    chans = 32
    srate = 1000.0
    fmt = pylsl.cf_float32

    info = pylsl.StreamInfo(
        name=name,
        type=strm_type,
        channel_count=chans,
        nominal_srate=srate,
        channel_format=fmt,
        source_id=None,
    )
    expected_src_id = str(hash((name, strm_type, chans, srate, fmt)))
    assert info.source_id() == expected_src_id

    # Augment info with desc
    info.desc().append_child_value("manufacturer", "pytest")
    chns = info.desc().append_child("channels")
    for chan_ix in range(1, chans + 1):
        ch = chns.append_child("channel")
        ch.append_child_value("label", f"Ch{chan_ix}")

    outlet = pylsl.StreamOutlet(info)
    outlet_info = outlet.get_info()

    """
    # See comment block in StreamOutlet.__init__ to see why this is commented out.
    import socket
    outlet_expected_source_id = str(hash((name, strm_type, chans, srate, fmt, socket.gethostname())))
    """
    outlet_expected_source_id = expected_src_id

    assert outlet_info.source_id() == outlet_expected_source_id
    out_desc = outlet_info.desc()
    assert out_desc.child_value("manufacturer") == "pytest"
    assert outlet_info.get_channel_labels() == [
        f"Ch{chan_ix}" for chan_ix in range(1, chans + 1)
    ]


@pytest.mark.skipif(
    not _has_reset_uid, reason="requires liblsl >= 1.18.0 (lsl_reset_uid)"
)
def test_reset_uid_generates_new_uid():
    info = pylsl.StreamInfo("T", "EEG", 4, 100, pylsl.cf_float32, source_id="src")
    # A locally-constructed info has no UID until reset (or until bound to an outlet).
    assert info.uid() == ""
    new_uid = info.reset_uid()
    assert new_uid != ""
    assert info.uid() == new_uid
    # A second reset yields a different value.
    assert info.reset_uid() != new_uid


@pytest.mark.skipif(
    _has_reset_uid, reason="only relevant when liblsl lacks lsl_reset_uid"
)
def test_reset_uid_raises_when_unavailable():
    info = pylsl.StreamInfo("T", "EEG", 4, 100, pylsl.cf_float32, source_id="src")
    with pytest.raises(NotImplementedError):
        info.reset_uid()
