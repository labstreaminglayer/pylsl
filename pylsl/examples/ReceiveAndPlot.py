import numpy as np
import math
import pylsl
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from typing import List

plot_duration = 5
update_interval = 60
pull_interval = 500  # ms between each pull operation


class Inlet:
    __slots__ = ['channel_count', 'inlet', 'name']
    
    def __init__(self, info: pylsl.StreamInfo):
        self.inlet = pylsl.StreamInlet(info, max_buflen=plot_duration,
                                       processing_flags=pylsl.proc_clocksync | pylsl.proc_dejitter)
        self.name = info.name()
        self.channel_count = info.channel_count()

    def pull_and_plot(self, plot_time, plt):
        pass


class DataInlet(Inlet):
    dtypes = [[], np.float32, np.float64, None, np.int32, np.int16, np.int8, np.int64]
    __slots__ = ['buffer', 'curves']

    def __init__(self, info: pylsl.StreamInfo, plt: pg.PlotItem):
        super().__init__(info)
        bufsize = (2*math.ceil(info.nominal_srate()*plot_duration), info.channel_count())
        self.buffer = np.empty(bufsize, dtype=self.dtypes[info.channel_format()])
        empty = np.array([])
        self.curves = [pg.PlotCurveItem(x=empty, y=empty, autoDownsample=True) for _ in range(self.channel_count)]
        for curve in self.curves:
            plt.addItem(curve)

    def pull_and_plot(self, plot_time, plt):
        _, ts = self.inlet.pull_chunk(timeout=0.0,
                                      max_samples=self.buffer.shape[0],
                                      dest_obj=self.buffer)
        if ts:
            ts = np.asarray(ts)
            y = self.buffer[0:ts.size, :]
            this_x = None
            old_offset = 0
            new_offset = 0
            for ch_ix in range(self.channel_count):
                old_x, old_y = self.curves[ch_ix].getData()
                if ch_ix == 0:
                    old_offset = old_x.searchsorted(plot_time)
                    new_offset = ts.searchsorted(plot_time)
                    this_x = np.hstack((old_x[old_offset:], ts[new_offset:]))
                this_y = np.hstack((old_y[old_offset:], y[new_offset:, ch_ix] - ch_ix))
                self.curves[ch_ix].setData(this_x, this_y)


class MarkerInlet(Inlet):
    def __init__(self, info: pylsl.StreamInfo):
        super().__init__(info)

    def pull_and_plot(self, plot_time, plt):
        # TODO: purge old markers
        strings, timestamps = self.inlet.pull_chunk(0)
        if timestamps:
            for string, ts in zip(strings, timestamps):
                plt.addItem(pg.InfiniteLine(ts, angle=90, movable=False, label=string[0]))


def main():
    # first resolve an EEG stream on the lab network
    inlets: List[Inlet] = []
    print("looking for streams")
    streams = pylsl.resolve_streams()

    # Create the pyqtgraph window
    pw = pg.plot(title='LSL Plot')
    plt = pw.getPlotItem()
    plt.enableAutoRange(x=False, y=True)

    for info in streams:
        if info.type() == 'Markers':
            if info.nominal_srate() != pylsl.IRREGULAR_RATE \
                    or info.channel_format() != pylsl.cf_string:
                print('Invalid marker stream ' + info.name())
            print('Adding marker inlet: ' + info.name())
            inlets.append(MarkerInlet(info))
        elif info.nominal_srate() != pylsl.IRREGULAR_RATE \
                and info.channel_format() != pylsl.cf_string:
            print('Adding data inlet: ' + info.name())
            inlets.append(DataInlet(info, plt))
        else:
            print('Don\'t know what to do with stream ' + info.name())

    def scroll():
        fudge_factor = pull_interval * .002
        plot_time = pylsl.local_clock()
        pw.setXRange(plot_time - plot_duration + fudge_factor, plot_time - fudge_factor)

    def update():
        # Read data from the inlet. Use a timeout of 0.0 so we don't block GUI interaction.
        current_inlet = 0
        mintime = pylsl.local_clock()
        for inlet in inlets:
            inlet.pull_and_plot(mintime - plot_duration, plt)

    update_timer = QtCore.QTimer()
    update_timer.timeout.connect(scroll)
    update_timer.start(update_interval)

    pull_timer = QtCore.QTimer()
    pull_timer.timeout.connect(update)
    pull_timer.start(pull_interval)

    import sys

    # Start Qt event loop unless running in interactive mode or using pyside.
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()


if __name__ == '__main__':
    main()
