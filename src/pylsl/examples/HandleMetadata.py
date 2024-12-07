"""Example program that shows how to attach meta-data to a stream, and how to
later on retrieve the meta-data again at the receiver side."""

import time

import numpy as np
from pylsl import StreamInfo, StreamInlet, StreamOutlet, resolve_byprop


def main():
    # create a new StreamInfo object which shall describe our stream
    info = StreamInfo("MetaTester", "EEG", 8, 100, "float32", "myuid56872")

    # now attach some meta-data (in accordance with XDF format,
    # see also https://github.com/sccn/xdf/wiki/Meta-Data)
    chns = info.desc().append_child("channels")
    ch_labels = ["C3", "C4", "Cz", "FPz", "POz", "CPz", "O1", "O2"]
    for label in ch_labels:
        ch = chns.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    info.desc().append_child_value("manufacturer", "SCCN")
    cap = info.desc().append_child("cap")
    cap.append_child_value("name", "EasyCap")
    cap.append_child_value("size", "54")
    cap.append_child_value("labelscheme", "10-20")

    # create outlet for the stream
    outlet = StreamOutlet(info)

    # Send a sample into the outlet...
    dummy_sample = np.arange(len(ch_labels), dtype=np.float32)
    outlet.push_sample(dummy_sample)

    # === the following could run on another computer ===

    # first we resolve a stream whose name is MetaTester (note that there are
    # other ways to query a stream, too - for instance by content-type)
    results = resolve_byprop("name", "MetaTester")

    # open an inlet so we can read the stream's data (and meta-data)
    inlet = StreamInlet(results[0])

    # get the full stream info (including custom meta-data) and dissect it
    info = inlet.info()
    print("The stream's XML meta-data is: ")
    print(info.as_xml())
    print("The manufacturer is: %s" % info.desc().child_value("manufacturer"))
    print("Cap circumference is: %s" % info.desc().child("cap").child_value("size"))
    print("The channel labels are as follows:")
    ch = info.desc().child("channels").child("channel")
    for k in range(info.channel_count()):
        print("  " + ch.child_value("label"))
        ch = ch.next_sibling()

    time.sleep(3)


if __name__ == "__main__":
    main()
