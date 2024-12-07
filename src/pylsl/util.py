import ctypes

from .lib import lib

# Constant to indicate that a stream has variable sampling rate.
IRREGULAR_RATE = 0.0

# Constant to indicate that a sample has the next successive time stamp
# according to the stream's defined sampling rate. Optional optimization to
# transmit less data per sample.
DEDUCED_TIMESTAMP = -1.0

# A very large time value (ca. 1 year); can be used in timeouts.
FOREVER = 32000000.0

# Value formats supported by LSL. LSL data streams are sequences of samples,
# each of which is a same-size vector of values with one of the below types.

# Post processing flags
proc_none = 0  # No automatic post-processing; return the ground-truth time stamps for manual post-processing.
proc_clocksync = 1  # Perform automatic clock synchronization; equivalent to manually adding the time_correction().
proc_dejitter = 2  # Remove jitter from time stamps using a smoothing algorithm to the received time stamps.
proc_monotonize = 4  # Force the time-stamps to be monotonically ascending. Only makes sense if timestamps are dejittered.
proc_threadsafe = 8  # Post-processing is thread-safe (same inlet can be read from by multiple threads).
proc_ALL = (
    proc_none | proc_clocksync | proc_dejitter | proc_monotonize | proc_threadsafe
)


def protocol_version():
    """Protocol version.

    The major version is protocol_version() / 100;
    The minor version is protocol_version() % 100;

    Clients with different minor versions are protocol-compatible with each
    other while clients with different major versions will refuse to work
    together.

    """
    return lib.lsl_protocol_version()


def library_version():
    """Version of the underlying liblsl library.

    The major version is library_version() / 100;
    The minor version is library_version() % 100;

    """
    return lib.lsl_library_version()


def library_info():
    """Get a string containing library information. The format of the string shouldn't be used
    for anything important except giving a a debugging person a good idea which exact library
    version is used."""
    return lib.lsl_library_info().decode("utf-8")


def local_clock():
    """Obtain a local system time stamp in seconds.

    The resolution is better than a millisecond. This reading can be used to
    assign time stamps to samples as they are being acquired.

    If the "age" of a sample is known at a particular time (e.g., from USB
    transmission delays), it can be used as an offset to lsl_local_clock() to
    obtain a better estimate of when a sample was actually captured. See
    StreamOutlet.push_sample() for a use case.

    """
    return lib.lsl_local_clock()


class TimeoutError(RuntimeError):
    # note: although this overrides the name of a built-in exception,
    #       this API is retained here for compatibility with the Python 2.x
    #       version of pylsl
    pass


class LostError(RuntimeError):
    pass


class InvalidArgumentError(RuntimeError):
    pass


class InternalError(RuntimeError):
    pass


def handle_error(errcode):
    """Error handler function. Translates an error code into an exception."""
    if type(errcode) is ctypes.c_int:
        errcode = errcode.value
    if errcode == 0:
        pass  # no error
    elif errcode == -1:
        raise TimeoutError("the operation failed due to a timeout.")
    elif errcode == -2:
        raise LostError("the stream has been lost.")
    elif errcode == -3:
        raise InvalidArgumentError("an argument was incorrectly specified.")
    elif errcode == -4:
        raise InternalError("an internal error has occurred.")
    elif errcode < 0:
        raise RuntimeError("an unknown error has occurred.")
