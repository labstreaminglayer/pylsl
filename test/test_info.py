import pylsl


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
