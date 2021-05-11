"""Example program to demonstrate how to send a multi-channel time-series
with proper meta-data to LSL."""
import sys
import getopt

import time
from random import random as rand

import pylsl


def main(argv):
    srate = 100
    name = 'LSLExampleAmp'
    stream_type = 'EEG'
    channel_names = ["C3", "C4", "Cz", "FPz", "POz", "CPz", "O1", "O2"]
    n_channels = len(channel_names)
    help_string = 'SendData.py -s <sampling_rate> -n <stream_name> -t <stream_type>'
    try:
        opts, args = getopt.getopt(argv, "hs:n:t:", longopts=["srate=", "name=", "type"])
    except getopt.GetoptError:
        print(help_string)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help_string)
            sys.exit()
        elif opt in ("-s", "--srate"):
            srate = float(arg)
        elif opt in ("-n", "--name"):
            name = arg
        elif opt in ("-t", "--type"):
            stream_type = arg

    # first create a new stream info (here we set the name to BioSemi,
    # the content-type to EEG, 8 channels, 100 Hz, and float-valued data) The
    # last value would be the serial number of the device or some other more or
    # less locally unique identifier for the stream as far as available (you
    # could also omit it but interrupted connections wouldn't auto-recover).
    info = pylsl.StreamInfo(name, stream_type, n_channels, srate, 'float32', 'myuid2424')

    # append some meta-data
    info.desc().append_child_value("manufacturer", "LSLExampleAmp")
    chns = info.desc().append_child("channels")
    for label in channel_names:
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    info.desc().append_child_value("manufacturer", "LSLExamples")
    cap = info.desc().append_child("cap")
    cap.append_child_value("name", "ComfyCap")
    cap.append_child_value("size", "54")
    cap.append_child_value("labelscheme", "10-20")

    # next make an outlet; we set the transmission chunk size to 32 samples and
    # the outgoing buffer size to 360 seconds (max.)
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
            # get a time stamp in seconds (we pretend that our samples are actually
            # 125ms old, e.g., as if coming from some external hardware)
            stamp = pylsl.local_clock() - 0.125
            # now send it and wait for a bit
            # Note that even though `rand()` returns a 64-bit value, the `push_chunk` method
            #  will convert it to c_float before passing the data to liblsl.
            outlet.push_chunk(mychunk, stamp)
            sent_samples += required_samples
        time.sleep(0.02)


if __name__ == '__main__':
    main(sys.argv[1:])
