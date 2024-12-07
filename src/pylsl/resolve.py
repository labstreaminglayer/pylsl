import ctypes

from .lib import lib
from .info import StreamInfo
from .util import FOREVER


def resolve_streams(wait_time=1.0):
    """Resolve all streams on the network.

    This function returns all currently available streams from any outlet on
    the network. The network is usually the subnet specified at the local
    router, but may also include a group of machines visible to each other via
    multicast packets (given that the network supports it), or list of
    hostnames. These details may optionally be customized by the experimenter
    in a configuration file (see Network Connectivity in the LSL wiki).

    Keyword arguments:
    wait_time -- The waiting time for the operation, in seconds, to search for
                 streams. Warning: If this is too short (<0.5s) only a subset
                 (or none) of the outlets that are present on the network may
                 be returned. (default 1.0)

    Returns a list of StreamInfo objects (with empty desc field), any of which
    can subsequently be used to open an inlet. The full description can be
    retrieved from the inlet.

    """
    # noinspection PyCallingNonCallable
    buffer = (ctypes.c_void_p * 1024)()
    num_found = lib.lsl_resolve_all(
        ctypes.byref(buffer), 1024, ctypes.c_double(wait_time)
    )
    return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


def resolve_byprop(prop, value, minimum=1, timeout=FOREVER):
    """Resolve all streams with a specific value for a given property.

    If the goal is to resolve a specific stream, this method is preferred over
    resolving all streams and then selecting the desired one.

    Keyword arguments:
    prop -- The StreamInfo property that should have a specific value (e.g.,
            "name", "type", "source_id", or "desc/manufacturer").
    value -- The string value that the property should have (e.g., "EEG" as
             the type property).
    minimum -- Return at least this many streams. (default 1)
    timeout -- Optionally a timeout of the operation, in seconds. If the
               timeout expires, less than the desired number of streams
               (possibly none) will be returned. (default FOREVER)

    Returns a list of matching StreamInfo objects (with empty desc field), any
    of which can subsequently be used to open an inlet.

    Example: results = resolve_Stream_byprop("type","EEG")

    """
    # noinspection PyCallingNonCallable
    buffer = (ctypes.c_void_p * 1024)()
    num_found = lib.lsl_resolve_byprop(
        ctypes.byref(buffer),
        1024,
        ctypes.c_char_p(str.encode(prop)),
        ctypes.c_char_p(str.encode(value)),
        minimum,
        ctypes.c_double(timeout),
    )
    return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


def resolve_bypred(predicate, minimum=1, timeout=FOREVER):
    """Resolve all streams that match a given predicate.

    Advanced query that allows to impose more conditions on the retrieved
    streams; the given string is an XPath 1.0 predicate for the <description>
    node (omitting the surrounding []'s), see also
    http://en.wikipedia.org/w/index.php?title=XPath_1.0&oldid=474981951.

    Keyword arguments:
    predicate -- The predicate string, e.g. "name='BioSemi'" or
                "type='EEG' and starts-with(name,'BioSemi') and
                 count(description/desc/channels/channel)=32"
    minimum -- Return at least this many streams. (default 1)
    timeout -- Optionally a timeout of the operation, in seconds. If the
               timeout expires, less than the desired number of streams
               (possibly none) will be returned. (default FOREVER)

    Returns a list of matching StreamInfo objects (with empty desc field), any
    of which can subsequently be used to open an inlet.

    """
    # noinspection PyCallingNonCallable
    buffer = (ctypes.c_void_p * 1024)()
    num_found = lib.lsl_resolve_bypred(
        ctypes.byref(buffer),
        1024,
        ctypes.c_char_p(str.encode(predicate)),
        minimum,
        ctypes.c_double(timeout),
    )
    return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


class ContinuousResolver:
    """A convenience class resolving streams continuously in the background.

    This object can be queried at any time for the set of streams that are
    currently visible on the network.

    """

    def __init__(self, prop=None, value=None, pred=None, forget_after=5.0):
        """Construct a new continuous_resolver.

        Keyword arguments:
        forget_after -- When a stream is no longer visible on the network
                        (e.g., because it was shut down), this is the time in
                        seconds after which it is no longer reported by the
                        resolver.

        """
        if pred is not None:
            if prop is not None or value is not None:
                raise ValueError(
                    "you can only either pass the prop/value "
                    "argument or the pred argument, but not "
                    "both."
                )
            self.obj = lib.lsl_create_continuous_resolver_bypred(
                str.encode(pred), ctypes.c_double(forget_after)
            )
        elif prop is not None and value is not None:
            self.obj = lib.lsl_create_continuous_resolver_byprop(
                str.encode(prop), str.encode(value), ctypes.c_double(forget_after)
            )
        elif prop is not None or value is not None:
            raise ValueError(
                "if prop is specified, then value must be "
                "specified, too, and vice versa."
            )
        else:
            self.obj = lib.lsl_create_continuous_resolver(ctypes.c_double(forget_after))
        self.obj = ctypes.c_void_p(self.obj)
        if not self.obj:
            raise RuntimeError("could not create continuous resolver.")

    def __del__(self):
        """Destructor for the continuous resolver."""
        # noinspection PyBroadException
        try:
            lib.lsl_destroy_continuous_resolver(self.obj)
        except Exception:
            pass

    def results(self):
        """Obtain the set of currently present streams on the network.

        Returns a list of matching StreamInfo objects (with empty desc
        field), any of which can subsequently be used to open an inlet.

        """
        # noinspection PyCallingNonCallable
        buffer = (ctypes.c_void_p * 1024)()
        num_found = lib.lsl_resolver_results(self.obj, ctypes.byref(buffer), 1024)
        return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


def resolve_stream(*args):
    if len(args) == 0:
        return resolve_streams()
    elif type(args[0]) in [int, float]:
        return resolve_streams(args[0])
    elif type(args[0]) is str:
        if len(args) == 1:
            return resolve_bypred(args[0])
        elif type(args[1]) in [int, float]:
            return resolve_bypred(args[0], args[1])
        else:
            if len(args) == 2:
                return resolve_byprop(args[0], args[1])
            else:
                return resolve_byprop(args[0], args[1], args[2])
