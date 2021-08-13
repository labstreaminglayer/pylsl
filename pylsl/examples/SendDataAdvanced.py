"""Example program to demonstrate how to send a multi-channel time-series
with proper meta-data to LSL."""
import argparse
import time
from random import random as rand

import pylsl


def main(name='LSLExampleAmp', stream_type='EEG', srate=100):

    channel_names = ["Fp1", "Fp2", "C3", "C4", "Cz", "P3", "P4", "Pz", "O1", "O2"]
    channel_locations = [
        [-0.0307, 0.0949, -0.0047],
        [0.0307, 0.0949, -0.0047],
        [-0.0742,  4.54343962e-18,  0.0668],
        [0.0743, 4.54956286e-18, 0.0669],
        [0, 6.123234e-18, 0.1],
        [-0.0567, -0.0677,  0.0469],
        [0.0566, -0.0677,  0.0469],
        [8.74397815e-18, -0.0714,  0.0699],
        [-0.0307, -0.0949, -0.0047],
        [0.0307, -0.0949, -0.0047]
    ]
    n_channels = len(channel_names)

    # First create a new stream info.
    #  The first 4 arguments are stream name, stream type, number of channels, and
    #  sampling rate -- all parameterized by the keyword arguments or the channel list above.
    #  For this example, we will always use float32 data so we provide that as the 5th parameter.
    #  The last value would be the serial number of the device or some other more or
    #  less locally unique identifier for the stream as far as available (you
    #  could also omit it but interrupted connections wouldn't auto-recover).
    info = pylsl.StreamInfo(name, stream_type, n_channels, srate, 'float32', 'myuid2424')

    # append some meta-data
    # https://github.com/sccn/xdf/wiki/EEG-Meta-Data
    info.desc().append_child_value("manufacturer", "LSLExampleAmp")
    chns = info.desc().append_child("channels")
    for chan_ix, label in enumerate(channel_names):
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
        ch.append_child_value("scaling_factor", "1")
        loc = ch.append_child("location")
        for ax_str, pos in zip(["X", "Y", "Z"], channel_locations[chan_ix]):
            loc.append_child_value(ax_str, str(pos))
    cap = info.desc().append_child("cap")
    cap.append_child_value("name", "ComfyCap")
    cap.append_child_value("size", "54")
    cap.append_child_value("labelscheme", "10-20")

    # next make an outlet; we set the transmission chunk size to 32 samples
    # and the outgoing buffer size to 360 seconds (max.)
    outlet = pylsl.StreamOutlet(info, 32, 360)

    if False:
        # It's unnecessary to check the info when the stream was created in the same scope; just use info.
        # Use this code only as a sanity check if you think something when wrong during stream creation.
        check_info = outlet.get_info()
        assert check_info.name() == name
        assert check_info.type() == stream_type
        assert check_info.channel_count() == len(channel_names)
        assert check_info.channel_format() == pylsl.cf_float32
        assert check_info.nominal_srate() == srate

    print("now sending data...")
    start_time = pylsl.local_clock()
    sent_samples = 0
    while True:
        elapsed_time = pylsl.local_clock() - start_time
        required_samples = int(srate * elapsed_time) - sent_samples
        if required_samples > 0:
            # make a chunk==array of length required_samples, where each element in the array
            # is a new random n_channels sample vector
            mychunk = [[rand() for chan_ix in range(n_channels)]
                       for samp_ix in range(required_samples)]
            # Get a time stamp in seconds. We pretend that our samples are actually
            # 125ms old, e.g., as if coming from some external hardware with known latency.
            stamp = pylsl.local_clock() - 0.125
            # now send it and wait for a bit
            # Note that even though `rand()` returns a 64-bit value, the `push_chunk` method
            #  will convert it to c_float before passing the data to liblsl.
            outlet.push_chunk(mychunk, stamp)
            sent_samples += required_samples
        time.sleep(0.02)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='LSLExampleAmp',
                        help="Name of the created stream.")
    parser.add_argument('--type', default='EEG',
                        help="Type of the created stream.")
    parser.add_argument('--srate', default=100.0, help="Sampling rate of the created stream.", type=float)
    arg = parser.parse_args()

    main(name=arg.name, stream_type=arg.type, srate=arg.srate)
