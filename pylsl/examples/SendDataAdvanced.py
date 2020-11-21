"""Example program to demonstrate how to send a multi-channel time-series
with proper meta-data to LSL."""
import sys
import getopt

import time
from random import random as rand

from pylsl import StreamInfo, StreamOutlet, local_clock


def main(argv):
    srate = 100
    name = 'BioSemi'
    type = 'EEG'
    n_channels = 8
    help_string = 'SendData.py -s <sampling_rate> -n <stream_name> -t <stream_type>'
    try:
        opts, args = getopt.getopt(argv, "hs:c:n:t:", longopts=["srate=", "channels=", "name=", "type"])
    except getopt.GetoptError:
        print(help_string)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help_string)
            sys.exit()
        elif opt in ("-s", "--srate"):
            srate = float(arg)
        elif opt in ("-c", "--channels"):
            n_channels = int(arg)
        elif opt in ("-n", "--name"):
            name = arg
        elif opt in ("-t", "--type"):
            type = arg

    # first create a new stream info (here we set the name to BioSemi,
    # the content-type to EEG, 8 channels, 100 Hz, and float-valued data) The
    # last value would be the serial number of the device or some other more or
    # less locally unique identifier for the stream as far as available (you
    # could also omit it but interrupted connections wouldn't auto-recover).
    info = StreamInfo(name, type, n_channels, srate, 'float32', 'myuid2424')

    # append some meta-data
    info.desc().append_child_value("manufacturer", "BioSemi")
    channels = info.desc().append_child("channels")
    for c in ["C3", "C4", "Cz", "FPz", "POz", "CPz", "O1", "O2"]:
        channels.append_child("channel") \
            .append_child_value("label", c) \
            .append_child_value("unit", "microvolts") \
            .append_child_value("type", "EEG")

    # next make an outlet; we set the transmission chunk size to 32 samples and
    # the outgoing buffer size to 360 seconds (max.)
    outlet = StreamOutlet(info, 32, 360)

    print("now sending data...")
    start_time = local_clock()
    sent_samples = 0
    while True:
        elapsed_time = local_clock() - start_time
        required_samples = int(srate * elapsed_time) - sent_samples
        if required_samples > 0:
            # make a chunk==array of length required_samples, where each element in the array
            # is a new random n_channels sample vector
            mychunk = [[rand() for chan_ix in range(n_channels)]
                       for samp_ix in range(required_samples)]
            # get a time stamp in seconds (we pretend that our samples are actually
            # 125ms old, e.g., as if coming from some external hardware)
            stamp = local_clock() - 0.125
            # now send it and wait for a bit
            outlet.push_chunk(mychunk, stamp)
        time.sleep(0.02)


if __name__ == '__main__':
    main(sys.argv[1:])
