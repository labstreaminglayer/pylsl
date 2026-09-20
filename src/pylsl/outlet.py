import ctypes

import numpy as np

from .lib import (
    lib,
    fmt2push_sample,
    fmt2push_chunk,
    fmt2push_chunk_n,
    fmt2type,
    fmt2npdtype,
    cf_string,
)
from .util import handle_error
from .info import StreamInfo


class StreamOutlet:
    """A stream outlet.

    Outlets are used to make streaming data (and the meta-data) available on
    the lab network.

    """

    def __init__(
        self,
        info: StreamInfo,
        chunk_size: int = 0,
        max_buffered: int = 360,
        transport_flags: int = 0,
    ):
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
        transport_flags -- Optional bitwise-OR combination of transport option
                        flags (the transp_* constants). For example,
                        transp_sync_blocking enables synchronous (zero-copy)
                        pushes for high-bandwidth streams. The default, 0
                        (transp_default), uses the standard asynchronous
                        transport. (default 0)

        """

        """
        # If the source_id matches the default then we can assume it was created automatically.
        # It may be desirable to include the host name in the source_id hash to avoid collisions.
        # However, there are likely implications to re-creating the info so this is commented out
        #  until a need arises.
        expected_src_id = str(hash((
            info.name(), info.type(), info.channel_count(), info.nominal_srate(), info.channel_format()
        )))
        if info.source_id() == expected_src_id:
            old_desc = info.desc()  # save the old metadata
            import socket
            new_source_id = str(hash((
                info.name(),
                info.type(),
                info.channel_count(),
                info.nominal_srate(),
                info.channel_format(),
                socket.gethostname()
            )))
            info = StreamInfo(
                name=info.name(),
                type=info.type(),
                channel_count=info.channel_count(),
                nominal_srate=info.nominal_srate(),
                channel_format=info.channel_format(),
                source_id=new_source_id,
            )
            # Add the old metadata to the new info object
            new_desc_parent = info.desc().parent()
            new_desc_parent.remove_child(info.desc())
            new_desc_parent.append_copy(old_desc)
        """
        if transport_flags:
            self.obj = lib.lsl_create_outlet_ex(
                info.obj, chunk_size, max_buffered, transport_flags
            )
        else:
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
        self.np_dtype = fmt2npdtype[self.channel_format]
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

    def push_sample(self, x, timestamp: float = 0.0, pushthrough: bool = True):
        """Push a sample into the outlet.

        Each entry in the list corresponds to one channel.

        Keyword arguments:
        x -- A list of values to push (one per channel).
        timestamp -- Optionally the capture time of the sample, in agreement
                     with local_clock(); if 0.0, the current
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

    def push_chunk(self, x, timestamp: float = 0.0, pushthrough: bool = True):
        """Push a list of samples into the outlet.

        samples -- A list of samples, preferably as a 2-D numpy array.
                   `samples` can also be a list of lists, or a list of
                   multiplexed values.
        timestamp -- Optional, float or 1-D list of floats.
                     If float and != 0.0: the capture time of the most recent sample, in
                     agreement with local_clock(); if default (0.0), the current
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

        if self.np_dtype is not None:
            # Numeric: go through numpy so lists, nested lists and arrays of
            # any dtype/layout all end up as one contiguous buffer in the
            # stream's dtype. A C-contiguous array of the right dtype is a
            # no-op view. `arr` must stay alive until the call returns.
            arr = np.ascontiguousarray(x, dtype=self.np_dtype)
            n_values = arr.size
            if n_values == 0:
                return  # don't send empty chunks
            bad_shape = arr.ndim == 2 and arr.shape[1] != self.channel_count
            if bad_shape or n_values % self.channel_count != 0:
                raise ValueError(
                    "Each sample must have the same number of channels ("
                    + str(self.channel_count)
                    + ")."
                )
            handle_error(
                liblsl_push_chunk_func(
                    self.obj,
                    ctypes.c_void_p(arr.ctypes.data),
                    ctypes.c_long(n_values),
                    timestamp_c,
                    ctypes.c_int(pushthrough),
                )
            )
            return
        # String streams: flatten, encode, and hand liblsl an array of char*.
        if len(x):
            if type(x[0]) is list:
                x = [v for sample in x for v in sample]
            n_values = len(x)
            if n_values % self.channel_count != 0:
                raise ValueError(
                    "Each sample must have the same number of channels ("
                    + str(self.channel_count)
                    + ")."
                )
            # One NUL-separated buffer plus a vectorised pointer table is far
            # cheaper than constructing a ctypes c_char_p array element by
            # element. `buf` and `ptrs` must outlive the call.
            encoded = [v.encode("utf-8") for v in x]
            buf = ctypes.create_string_buffer(b"\0".join(encoded) + b"\0")
            lengths = np.fromiter(map(len, encoded), dtype=np.uintp, count=n_values)
            ptrs = np.empty(n_values, dtype=np.uintp)
            ptrs[0] = 0
            np.cumsum(lengths[:-1] + 1, out=ptrs[1:])
            ptrs += ctypes.addressof(buf)
            handle_error(
                liblsl_push_chunk_func(
                    self.obj,
                    ctypes.c_void_p(ptrs.ctypes.data),
                    ctypes.c_long(n_values),
                    timestamp_c,
                    ctypes.c_int(pushthrough),
                )
            )

    def have_consumers(self) -> bool:
        """Check whether consumers are currently registered.

        While it does not hurt, there is technically no reason to push samples
        if there is no consumer.

        """
        return bool(lib.lsl_have_consumers(self.obj))

    def wait_for_consumers(self, timeout: float) -> bool:
        """Wait until some consumer shows up (without wasting resources).

        Returns True if the wait was successful, False if the timeout expired.

        """
        return bool(lib.lsl_wait_for_consumers(self.obj, ctypes.c_double(timeout)))

    def get_info(self) -> StreamInfo:
        outlet_info = lib.lsl_get_info(self.obj)
        return StreamInfo(handle=outlet_info)
