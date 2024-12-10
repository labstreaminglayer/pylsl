import ctypes

from .lib import lib, fmt2type, fmt2pull_sample, fmt2pull_chunk, cf_string
from .util import handle_error, FOREVER
from .info import StreamInfo


def free_char_p_array_memory(char_p_array, num_elements):
    pointers = ctypes.cast(char_p_array, ctypes.POINTER(ctypes.c_void_p))
    for p in range(num_elements):
        if pointers[p] is not None:  # only free initialized pointers
            lib.lsl_destroy_string(pointers[p])


class StreamInlet:
    """A stream inlet.

    Inlets are used to receive streaming data (and meta-data) from the lab
    network.

    """

    def __init__(
        self, info, max_buflen=360, max_chunklen=0, recover=True, processing_flags=0
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
            raise TypeError(
                "description needs to be of type StreamInfo, " "got a list."
            )
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
            sample = [v for v in self.sample]
            if self.channel_format == cf_string:
                sample = [v.decode("utf-8") for v in sample]
            if assign_to is not None:
                assign_to[:] = sample
            return sample, timestamp
        else:
            return None, None

    def pull_chunk(self, timeout=0.0, max_samples=1024, dest_obj=None):
        """Pull a chunk of samples from the inlet.

        Keyword arguments:
        timeout -- The timeout of the operation; if passed as 0.0, then only
                   samples available for immediate pickup will be returned.
                   (default 0.0)
        max_samples -- Maximum number of samples to return. (default
                       1024)
        dest_obj -- A Python object that supports the buffer interface.
                    If this is provided then the dest_obj will be updated in place
                    and the samples list returned by this method will be empty.
                    It is up to the caller to trim the buffer to the appropriate
                    number of samples.
                    A numpy buffer must be order='C'
                    (default None)

        Returns a tuple (samples,timestamps) where samples is a list of samples
        (each itself a list of values), and timestamps is a list of time-stamps.

        Throws a LostError if the stream source has been lost.

        """
        # look up a pre-allocated buffer of appropriate length
        num_channels = self.channel_count
        max_values = max_samples * num_channels

        if max_samples not in self.buffers:
            # noinspection PyCallingNonCallable
            self.buffers[max_samples] = (
                (self.value_type * max_values)(),
                (ctypes.c_double * max_samples)(),
            )
        if dest_obj is not None:
            data_buff = (self.value_type * max_values).from_buffer(dest_obj)
        else:
            data_buff = self.buffers[max_samples][0]
        ts_buff = self.buffers[max_samples][1]

        # read data into it
        errcode = ctypes.c_int()
        # noinspection PyCallingNonCallable
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
        # return results (note: could offer a more efficient format in the
        # future, e.g., a numpy array)
        num_samples = num_elements / num_channels
        if dest_obj is None:
            samples = [
                [data_buff[s * num_channels + c] for c in range(num_channels)]
                for s in range(int(num_samples))
            ]
            if self.channel_format == cf_string:
                samples = [[v.decode("utf-8") for v in s] for s in samples]
                free_char_p_array_memory(data_buff, max_values)
        else:
            samples = None
        timestamps = [ts_buff[s] for s in range(int(num_samples))]
        return samples, timestamps

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
