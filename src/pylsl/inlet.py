import ctypes
import operator

import numpy as np

from .lib import (
    lib,
    fmt2type,
    fmt2npdtype,
    fmt2pull_sample,
    fmt2pull_chunk,
    cf_string,
)
from .util import handle_error, FOREVER
from .info import StreamInfo


def free_char_p_array_memory(char_p_array, num_elements):
    """Free the first num_elements strings liblsl allocated into char_p_array.

    liblsl has no bulk-free call, so this is one lsl_destroy_string call per
    string. Reading the pointers through numpy avoids creating a ctypes
    object per element on top of that.
    """
    if num_elements == 0:
        return
    pointers = np.frombuffer(char_p_array, dtype=np.uintp, count=num_elements)
    destroy = lib.lsl_destroy_string
    for p in pointers[pointers != 0].tolist():  # only free initialized pointers
        destroy(p)


class StreamInlet:
    """A stream inlet.

    Inlets are used to receive streaming data (and meta-data) from the lab
    network.

    """

    def __init__(
        self,
        info,
        max_buflen=360,
        max_chunklen=0,
        recover=True,
        processing_flags=0,
        as_numpy=False,
    ):
        """Construct a new stream inlet from a resolved stream description.

        Keyword arguments:
        description -- A resolved stream description object (as coming from one
                of the resolver functions). Note: the stream_inlet may also be
                constructed with a fully-specified stream_info, if the desired
                channel format and count is already known up-front, but this is
                strongly discouraged and should only ever be done if there is
                no time to resolve the stream up-front (e.g., due to
                limitations in the client program).
        max_buflen -- Optionally the maximum amount of data to buffer (in
                      seconds if there is a nominal sampling rate, otherwise
                      x100 in samples). Recording applications want to use a
                      fairly large buffer size here, while real-time
                      applications would only buffer as much as they need to
                      perform their next calculation. (default 360)
        max_chunklen -- Optionally the maximum size, in samples, at which
                        chunks are transmitted (the default corresponds to the
                        chunk sizes used by the sender). Recording programs
                        can use a generous size here (leaving it to the network
                        how to pack things), while real-time applications may
                        want a finer (perhaps 1-sample) granularity. If left
                        unspecified (=0), the sender determines the chunk
                        granularity. (default 0)
        recover -- Try to silently recover lost streams that are recoverable
                   (=those that that have a source_id set). In all other cases
                   (recover is False or the stream is not recoverable)
                   functions may throw a lost_error if the stream's source is
                   lost (e.g., due to an app or computer crash). (default True)
        processing_flags -- Post-processing options. Use one of the post-processing
                   flags `proc_none`, `proc_clocksync`, `proc_dejitter`, `proc_monotonize`,
                   or `proc_threadsafe`. Can also be a logical OR combination of multiple
                   flags. Use `proc_ALL` for all flags. (default proc_none).
        """
        if type(info) is list:
            raise TypeError("description needs to be of type StreamInfo, got a list.")
        self.as_numpy = bool(as_numpy)
        self.obj = lib.lsl_create_inlet(info.obj, max_buflen, max_chunklen, recover)
        self.obj = ctypes.c_void_p(self.obj)
        if not self.obj:
            raise RuntimeError("could not create stream inlet.")
        if processing_flags > 0:
            handle_error(lib.lsl_set_postprocessing(self.obj, processing_flags))
        self.channel_format = info.channel_format()
        self.channel_count = info.channel_count()
        self.do_pull_sample = fmt2pull_sample[self.channel_format]
        self.do_pull_chunk = fmt2pull_chunk[self.channel_format]
        self.value_type = fmt2type[self.channel_format]
        self.np_dtype = fmt2npdtype[self.channel_format]
        self.sample_type = self.value_type * self.channel_count
        self.sample = self.sample_type()
        self.buffers = {}

    def __del__(self):
        """Destructor. The inlet will automatically disconnect if destroyed."""
        # noinspection PyBroadException
        try:
            lib.lsl_destroy_inlet(self.obj)
        except Exception:
            pass

    def info(self, timeout=FOREVER):
        """Retrieve the complete information of the given stream.

        This includes the extended description. Can be invoked at any time of
        the stream's lifetime.

        Keyword arguments:
        timeout -- Timeout of the operation. (default FOREVER)

        Throws a TimeoutError (if the timeout expires), or LostError (if the
        stream source has been lost).

        """
        errcode = ctypes.c_int()
        result = lib.lsl_get_fullinfo(
            self.obj, ctypes.c_double(timeout), ctypes.byref(errcode)
        )
        handle_error(errcode)
        return StreamInfo(handle=result)

    def open_stream(self, timeout=FOREVER):
        """Subscribe to the data stream.

        All samples pushed in at the other end from this moment onwards will be
        queued and eventually be delivered in response to pull_sample() or
        pull_chunk() calls. Pulling a sample without some preceding open_stream
        is permitted (the stream will then be opened implicitly).

        Keyword arguments:
        timeout -- Optional timeout of the operation (default FOREVER).

        Throws a TimeoutError (if the timeout expires), or LostError (if the
        stream source has been lost).

        """
        errcode = ctypes.c_int()
        lib.lsl_open_stream(self.obj, ctypes.c_double(timeout), ctypes.byref(errcode))
        handle_error(errcode)

    def close_stream(self):
        """Drop the current data stream.

        All samples that are still buffered or in flight will be dropped and
        transmission and buffering of data for this inlet will be stopped. If
        an application stops being interested in data from a source
        (temporarily or not) but keeps the outlet alive, it should call
        lsl_close_stream() to not waste unnecessary system and network
        resources.

        """
        lib.lsl_close_stream(self.obj)

    def time_correction(self, timeout=FOREVER):
        """Retrieve an estimated time correction offset for the given stream.

        The first call to this function takes several milliseconds until a
        reliable first estimate is obtained. Subsequent calls are instantaneous
        (and rely on periodic background updates). The precision of these
        estimates should be below 1 ms (empirically within +/-0.2 ms).

        Keyword arguments:
        timeout -- Timeout to acquire the first time-correction estimate
                   (default FOREVER).

        Returns the current time correction estimate. This is the number that
        needs to be added to a time stamp that was remotely generated via
        local_clock() to map it into the local clock domain of this
        machine.

        Throws a TimeoutError (if the timeout expires), or LostError (if the
        stream source has been lost).

        """
        errcode = ctypes.c_int()
        result = lib.lsl_time_correction(
            self.obj, ctypes.c_double(timeout), ctypes.byref(errcode)
        )
        handle_error(errcode)
        return result

    def pull_sample(self, timeout=FOREVER, sample=None):
        """Pull a sample from the inlet and return it.

        Keyword arguments:
        timeout -- The timeout for this operation, if any. (default FOREVER)
                   If this is passed as 0.0, then the function returns only a
                   sample if one is buffered for immediate pickup.

        Returns a tuple (sample,timestamp) where sample is a list of channel
        values and timestamp is the capture time of the sample on the remote
        machine, or (None,None) if no new sample was available. To remap this
        time stamp to the local clock, add the value returned by
        .time_correction() to it.

        Throws a LostError if the stream source has been lost. Note that, if
        the timeout expires, no TimeoutError is thrown (because this case is
        not considered an error).

        """

        # support for the legacy API
        if type(timeout) is list:
            assign_to = timeout
            timeout = sample if type(sample) is float else 0.0
        else:
            assign_to = None

        errcode = ctypes.c_int()
        timestamp = self.do_pull_sample(
            self.obj,
            ctypes.byref(self.sample),
            self.channel_count,
            ctypes.c_double(timeout),
            ctypes.byref(errcode),
        )
        handle_error(errcode)
        if timestamp:
            if self.channel_format == cf_string:
                sample = [v.decode("utf-8") for v in self.sample]
            else:
                sample = list(self.sample)
            if assign_to is not None:
                assign_to[:] = sample
            return sample, timestamp
        else:
            return None, None

    def pull_chunk(
        self,
        timeout=0.0,
        max_samples=1024,
        dest_obj=None,
        min_samples=None,
        as_numpy=None,
    ):
        """Pull a chunk of samples from the inlet.

        Keyword arguments:
        timeout -- The timeout of the operation; if passed as 0.0, then only
                   samples available for immediate pickup will be returned.
                   (default 0.0)
        max_samples -- Maximum number of samples to return. (default
                       1024)
        dest_obj -- Where the data lands. A writable object supporting the
                    buffer interface (e.g. a C-contiguous numpy array) with
                    room for max_samples * channel_count values in the
                    stream's dtype. liblsl writes into it directly. The
                    returned `samples` is then None (or, with as_numpy=True,
                    a view of dest_obj trimmed to the samples received).
                    Numeric streams only. (default None: pylsl allocates)
        min_samples -- Minimum number of samples to wait for before returning
                       the samples that are immediately available, up to
                       max_samples. Set this to 1 to wait up to timeout for the
                       first sample and then return without waiting for the
                       remainder of the chunk. If the timeout expires first,
                       fewer samples may be returned. The default of None
                       preserves the original behavior, which waits until
                       max_samples is reached or the timeout expires.

        as_numpy -- What comes back. If True, numeric streams return
                    `samples` as a 2-D numpy array of shape
                    (n_samples, n_channels) in the stream's dtype and
                    `timestamps` as a 1-D float64 array, skipping the
                    conversion to Python lists (much faster for wide
                    streams). If False, both are lists. String streams
                    always return lists. None (default) uses the inlet's
                    `as_numpy` setting, which defaults to False.

        The two keywords are independent: dest_obj chooses whose memory the
        data is written to, as_numpy chooses the type of the return values.

        Returns a tuple (samples, timestamps):
          - default: samples is a list of samples (each a list of values),
            timestamps is a list of floats.
          - as_numpy=True: samples is an (n_samples, n_channels) array,
            timestamps a float64 array.
          - dest_obj given: samples is None, or with as_numpy=True a view of
            dest_obj covering the first n_samples samples.

        Throws a LostError if the stream source has been lost.

        """
        if as_numpy is None:
            as_numpy = self.as_numpy
        as_numpy = bool(as_numpy) and self.np_dtype is not None
        if min_samples is None:
            return self._pull_chunk_once(timeout, max_samples, dest_obj, as_numpy)

        try:
            min_samples = operator.index(min_samples)
        except TypeError:
            raise TypeError("min_samples must be an integer or None") from None
        if not 1 <= min_samples <= max_samples:
            raise ValueError("min_samples must be between 1 and max_samples")

        # liblsl's fixed-buffer pull waits for max_samples or timeout. First
        # make that target min_samples, then drain whatever else is already
        # available without blocking. This retains the existing behavior when
        # min_samples is omitted while providing a low-latency mode when it is 1.
        samples, timestamps = self._pull_chunk_once(
            timeout, min_samples, dest_obj, as_numpy
        )
        num_samples = len(timestamps)
        remaining = max_samples - num_samples
        if num_samples == 0 or remaining == 0:
            return samples, timestamps

        if dest_obj is not None:
            bytes_per_sample = ctypes.sizeof(self.value_type) * self.channel_count
            dest_view = memoryview(dest_obj).cast("B")[num_samples * bytes_per_sample :]
        else:
            dest_view = None

        more_samples, more_timestamps = self._pull_chunk_once(
            0.0, remaining, dest_view, as_numpy
        )
        if as_numpy:
            timestamps = np.concatenate((timestamps, more_timestamps))
            if dest_obj is not None:
                # Keep the contract: a single view over dest_obj, not a copy.
                samples = self._dest_view(dest_obj, len(timestamps))
            elif samples is not None:
                samples = np.concatenate((samples, more_samples))
        else:
            if samples is not None:
                samples.extend(more_samples)
            timestamps.extend(more_timestamps)
        return samples, timestamps

    def _pull_chunk_once(self, timeout, max_samples, dest_obj, as_numpy=False):
        """Perform one fixed-buffer liblsl chunk pull. See pull_chunk."""
        num_channels = self.channel_count
        max_values = max_samples * num_channels
        errcode = ctypes.c_int()

        if self.np_dtype is None:
            # String streams: liblsl fills an array of char* which we decode
            # and then free. Reuse a buffer per max_samples.
            if max_samples not in self.buffers:
                self.buffers[max_samples] = (
                    (self.value_type * max_values)(),
                    (ctypes.c_double * max_samples)(),
                )
            data_buff, ts_buff = self.buffers[max_samples]
            num_elements = self.do_pull_chunk(
                self.obj,
                ctypes.byref(data_buff),
                ctypes.byref(ts_buff),
                ctypes.c_size_t(max_values),
                ctypes.c_size_t(max_samples),
                ctypes.c_double(timeout),
                ctypes.byref(errcode),
            )
            handle_error(errcode)
            num_samples = num_elements // num_channels
            flat = [v.decode("utf-8") for v in data_buff[:num_elements]]
            free_char_p_array_memory(data_buff, num_elements)
            samples = [
                flat[s * num_channels : (s + 1) * num_channels]
                for s in range(num_samples)
            ]
            return samples, ts_buff[:num_samples]

        # Numeric streams: pull straight into numpy memory. Fresh arrays are
        # cheap, and an as_numpy result must never alias a reused buffer.
        ts_arr = np.empty(max_samples, dtype=np.float64)
        if dest_obj is not None:
            data_ptr = (self.value_type * max_values).from_buffer(dest_obj)
            data_arr = None
        else:
            data_arr = np.empty((max_samples, num_channels), dtype=self.np_dtype)
            data_ptr = ctypes.c_void_p(data_arr.ctypes.data)
        num_elements = self.do_pull_chunk(
            self.obj,
            data_ptr,
            ctypes.c_void_p(ts_arr.ctypes.data),
            ctypes.c_size_t(max_values),
            ctypes.c_size_t(max_samples),
            ctypes.c_double(timeout),
            ctypes.byref(errcode),
        )
        handle_error(errcode)
        num_samples = num_elements // num_channels
        timestamps = ts_arr[:num_samples]
        if as_numpy:
            if data_arr is None:
                return self._dest_view(dest_obj, num_samples), timestamps
            return data_arr[:num_samples], timestamps
        return (
            None if data_arr is None else data_arr[:num_samples].tolist(),
            timestamps.tolist(),
        )

    def _dest_view(self, dest_obj, num_samples):
        """A (num_samples, n_channels) numpy view over the start of dest_obj."""
        return np.frombuffer(
            dest_obj, dtype=self.np_dtype, count=num_samples * self.channel_count
        ).reshape(num_samples, self.channel_count)

    def samples_available(self):
        """Query whether samples are currently available for immediate pickup.

        Note that it is not a good idea to use samples_available() to determine
        whether a pull_*() call would block: to be sure, set the pull timeout
        to 0.0 or an acceptably low value. If the underlying implementation
        supports it, the value will be the number of samples available
        (otherwise it will be 1 or 0).

        """
        return lib.lsl_samples_available(self.obj)

    def flush(self):
        """
        Drop all queued not-yet pulled samples.
        :return: The number of dropped samples.
        """
        return lib.lsl_inlet_flush(self.obj)

    def was_clock_reset(self):
        """Query whether the clock was potentially reset since the last call.

        This is rarely-used function is only needed for applications that
        combine multiple time_correction values to estimate precise clock
        drift if they should tolerate cases where the source machine was
        hot-swapped or restarted.

        """
        return bool(lib.lsl_was_clock_reset(self.obj))
