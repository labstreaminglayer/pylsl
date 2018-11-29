"""Example program to show how to read a multi-channel time series from LSL."""

from pylsl import StreamInlet, resolve_stream
import time

# first resolve an EEG stream on the lab network
print("looking for an EEG stream...")
streams = resolve_stream('type', 'EEG')
info = streams[0]

# create a new inlet to read from the stream
inlet = StreamInlet(info)

print('Connected to outlet ' + info.name() + '@' + info.hostname())
while True:
    offset = inlet.time_correction()
    print('Offset: ' + str(offset))
    time.sleep(1)
