import ctypes

from .lib import (
    lib,
    fmt2push_sample,
    fmt2push_chunk,
    fmt2push_chunk_n,
    fmt2type,
    cf_string,
)
from .util import handle_error
from .info import StreamInfo


class StreamOutlet:
    """A stream outlet.

    Outlets are used to make streaming data (and the meta-data) available on
    the lab network.

    """

    def __init__(self, info, chunk_size=0, max_buffered=360):
        """Establish a new stream outlet. This makes the stream discoverable.

        Keyword arguments:
        description -- The StreamInfo object to describe this stream. Stays
                constant over the lifetime of the outlet.
        chunk_size --- Optionally the desired chunk granularity (in samples)
                       for transmission. If unspecified, each push operation
                       yields one chunk. Inlets can override this setting.
                       (default 0)
        max_buffered -- Optionally the maximum amount of data to buffer (in
                        seconds if there is a nominal sampling rate, otherwise
                        x100 in samples). The default is 6 minutes of data.
                        Note that, for high-bandwidth data, you will want to
                        use a lower value here to avoid running out of RAM.
                        (default 360)

        """
        self.obj = lib.lsl_create_outlet(info.obj, chunk_size, max_buffered)
        self.obj = ctypes.c_void_p(self.obj)
        if not self.obj:
            raise RuntimeError("could not create stream outlet.")
        self.channel_format = info.channel_format()
        self.channel_count = info.channel_count()
        self.do_push_sample = fmt2push_sample[self.channel_format]
        self.do_push_chunk = fmt2push_chunk[self.channel_format]
        self.do_push_chunk_n = fmt2push_chunk_n[self.channel_format]
        self.value_type = fmt2type[self.channel_format]
        self.sample_type = self.value_type * self.channel_count

    def __del__(self):
        """Destroy an outlet.

        The outlet will no longer be discoverable after destruction and all
        connected inlets will stop delivering data.

        """
        # noinspection PyBroadException
        try:
            lib.lsl_destroy_outlet(self.obj)
        except Exception as e:
            print(f"StreamOutlet deletion triggered error: {e}")

    def push_sample(self, x, timestamp=0.0, pushthrough=True):
        """Push a sample into the outlet.

        Each entry in the list corresponds to one channel.

        Keyword arguments:
        x -- A list of values to push (one per channel).
        timestamp -- Optionally the capture time of the sample, in agreement
                     with local_clock(); if omitted, the current
                     time is used. (default 0.0)
        pushthrough -- Whether to push the sample through to the receivers
                       instead of buffering it with subsequent samples.
                       Note that the chunk_size, if specified at outlet
                       construction, takes precedence over the pushthrough flag.
                       (default True)

        """
        if len(x) == self.channel_count:
            if self.channel_format == cf_string:
                x = [v.encode("utf-8") for v in x]
            handle_error(
                self.do_push_sample(
                    self.obj,
                    self.sample_type(*x),
                    ctypes.c_double(timestamp),
                    ctypes.c_int(pushthrough),
                )
            )
        else:
            raise ValueError(
                "length of the sample (" + str(len(x)) + ") must "
                "correspond to the stream's channel count ("
                + str(self.channel_count)
                + ")."
            )

    def push_chunk(self, x, timestamp=0.0, pushthrough=True):
        """Push a list of samples into the outlet.

        samples -- A list of samples, preferably as a 2-D numpy array.
                   `samples` can also be a list of lists, or a list of
                   multiplexed values.
        timestamp -- Optional, float or 1-D list of floats.
                     If float: the capture time of the most recent sample, in
                     agreement with local_clock(); if omitted/default (0.0), the current
                     time is used. The time stamps of other samples are
                     automatically derived according to the sampling rate of
                     the stream.
                     If list of floats: the time stamps for each sample.
                     Must be the same length as `samples`.
        pushthrough Whether to push the chunk through to the receivers instead
                    of buffering it with subsequent samples. Note that the
                    chunk_size, if specified at outlet construction, takes
                    precedence over the pushthrough flag. (default True)

        Note: performance is optimized for the following argument types:
            - `samples`: 2-D numpy array
            - `timestamp`: float
        """
        # Convert timestamp to corresponding ctype
        try:
            timestamp_c = ctypes.c_double(timestamp)
            # Select the corresponding push_chunk method
            liblsl_push_chunk_func = self.do_push_chunk
        except TypeError:
            try:
                timestamp_c = (ctypes.c_double * len(timestamp))(*timestamp)
                liblsl_push_chunk_func = self.do_push_chunk_n
            except TypeError:
                raise TypeError("timestamp must be a float or an iterable of floats")

        try:
            n_values = self.channel_count * len(x)
            data_buff = (self.value_type * n_values).from_buffer(x)
            handle_error(
                liblsl_push_chunk_func(
                    self.obj,
                    data_buff,
                    ctypes.c_long(n_values),
                    timestamp_c,
                    ctypes.c_int(pushthrough),
                )
            )
        except TypeError:
            # don't send empty chunks
            if len(x):
                if type(x[0]) is list:
                    x = [v for sample in x for v in sample]
                if self.channel_format == cf_string:
                    x = [v.encode("utf-8") for v in x]
                if len(x) % self.channel_count == 0:
                    # x is a flattened list of multiplexed values
                    constructor = self.value_type * len(x)
                    # noinspection PyCallingNonCallable
                    handle_error(
                        liblsl_push_chunk_func(
                            self.obj,
                            constructor(*x),
                            ctypes.c_long(len(x)),
                            timestamp_c,
                            ctypes.c_int(pushthrough),
                        )
                    )
                else:
                    raise ValueError(
                        "Each sample must have the same number of channels ("
                        + str(self.channel_count)
                        + ")."
                    )

    def have_consumers(self):
        """Check whether consumers are currently registered.

        While it does not hurt, there is technically no reason to push samples
        if there is no consumer.

        """
        return bool(lib.lsl_have_consumers(self.obj))

    def wait_for_consumers(self, timeout):
        """Wait until some consumer shows up (without wasting resources).

        Returns True if the wait was successful, False if the timeout expired.

        """
        return bool(lib.lsl_wait_for_consumers(self.obj, ctypes.c_double(timeout)))

    def get_info(self):
        outlet_info = lib.lsl_get_info(self.obj)
        return StreamInfo(handle=outlet_info)
