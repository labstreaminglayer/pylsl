"""Python API for the lab streaming layer.

The lab streaming layer provides a set of functions to make instrument data
accessible in real time within a lab network. From there, streams can be
picked up by recording programs, viewing programs or custom experiment
applications that access data streams in real time.

The API covers two areas:
- The "push API" allows to create stream outlets and to push data (regular
  or irregular measurement time series, event data, coded audio/video frames,
  etc.) into them.
- The "pull API" allows to create stream inlets and read time-synched
  experiment data from them (for recording, viewing or experiment control).

pylsl has been tested with Python 2.7 and 3.4.

"""

import os
import platform
import struct
from ctypes import (
    CDLL,
    POINTER,
    byref,
    c_byte,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_long,
    c_longlong,
    c_short,
    c_size_t,
    c_void_p,
    cast,
    util,
)
from enum import IntEnum

__all__ = [
    "IRREGULAR_RATE",
    "DEDUCED_TIMESTAMP",
    "FOREVER",
    "ChannelValueFormats",
    "PostProcessingFlags",
    "cf_float32",
    "cf_double64",
    "cf_string",
    "cf_int32",
    "cf_int16",
    "cf_int8",
    "cf_int64",
    "cf_undefined",
    "protocol_version",
    "library_version",
    "library_info",
    "local_clock",
    "StreamInfo",
    "StreamOutlet",
    "resolve_streams",
    "resolve_byprop",
    "resolve_bypred",
    "StreamInlet",
    "XMLElement",
    "ContinuousResolver",
    "TimeoutError",
    "LostError",
    "InvalidArgumentError",
    "InternalError",
    "stream_info",
    "stream_outlet",
    "stream_inlet",
    "xml_element",
    "timeout_error",
    "lost_error",
    "vectorf",
    "vectord",
    "vectorl",
    "vectori",
    "vectors",
    "vectorc",
    "vectorstr",
    "resolve_stream",
]

# =================
# === Constants ===
# =================

# Constant to indicate that a stream has variable sampling rate.
IRREGULAR_RATE = 0.0

# Constant to indicate that a sample has the next successive time stamp
# according to the stream's defined sampling rate. Optional optimization to
# transmit less data per sample.
DEDUCED_TIMESTAMP = -1.0

# A very large time value (ca. 1 year); can be used in timeouts.
FOREVER = 32000000.0


class ChannelValueFormats(IntEnum):
    """
    An enum class for the value formats supported by LSL. 
    LSL data streams are sequences of samples, each of which is a same-size vector of the below types.
    """

    UNDEFINED = 0
    """
    Cannot be transmitted.
    """

    FLOAT32 = 1
    """
    For up to 24-bit precision measurements in the appropriate physical unit (e.g. microvolts). 
    Integers from -16777216 to 16777216 are represented accurately.
    """

    DOUBLE64 = 2
    """
    For universal numeric data as long as permitted by network and disk budget.
    The largest representable integer is 53-bit.
    """

    STRING = 3
    """
    For variable-length ASCII strings or data blobs, such as video frames, complex event descriptions, etc.
    """

    INT32 = 4
    """
    For high-rate digitized formats that require 32-bit precision. 
    Depends critically on meta-data to represent meaningful units.
    Useful for application event codes or other coded data.
    """

    INT16 = 5
    """
    For very high bandwidth signals or CD quality audio (for professional audio float is recommended).
    """

    INT8 = 6
    """
    For binary signals or other coded data.
    """

    INT64 = 7
    """
    For now only for future compatibility. 
    Support for this type is not available on all languages and platforms.
    """


class PostProcessingFlags(IntEnum):
    """
    An enum class for the post-processing flags supported by LSL.
    """

    NONE = 0
    """
    No automatic post-processing; return the ground-truth time stamps for manual post-processing.
    """

    CLOCKSYNC = 1
    """
    Perform automatic clock synchronization; equivalent to manually adding the time_correction().
    """

    DEJITTER = 2
    """
    Remove jitter from time stamps using a smoothing algorithm to the received time stamps.
    """

    MONOTONIZE = 4
    """
    Force the time-stamps to be monotonically ascending. Only makes sense if timestamps are dejittered.
    """

    THREADSAFE = 8
    """
    Post-processing is thread-safe (same inlet can be read from by multiple threads).
    """

    ALL = NONE | THREADSAFE | DEJITTER | MONOTONIZE | THREADSAFE
    """
    All post-processing flags
    """


# ==========================================================
# === Free Functions provided by the lab streaming layer ===
# ==========================================================


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


# ==========================
# === Stream Declaration ===
# ==========================


class StreamInfo:
    """The StreamInfo object stores the declaration of a data stream.

    Represents the following information:
     a) stream data format (#channels, channel format)
     b) core information (stream name, content type, sampling rate)
     c) optional meta-data about the stream content (channel labels,
        measurement units, etc.)

    Whenever a program wants to provide a new stream on the lab network it will
    typically first create a StreamInfo to describe its properties and then
    construct a StreamOutlet with it to create the stream on the network.
    Recipients who discover the outlet can query the StreamInfo; it is also
    written to disk when recording the stream (playing a similar role as a file
    header).

    """

    def __init__(
            self,
            name="untitled",
            type="",
            channel_count=1,
            nominal_srate=IRREGULAR_RATE,
            channel_format=ChannelValueFormats.FLOAT32.value,
            source_id="",
            handle=None,
    ):
        """Construct a new StreamInfo object.

        Core stream information is specified here. Any remaining meta-data can
        be added later.

        Keyword arguments:
        name -- Name of the stream. Describes the device (or product series)
                that this stream makes available (for use by programs,
                experimenters or data analysts). Cannot be empty.
        type -- Content type of the stream. By convention LSL uses the content
                types defined in the XDF file format specification where
                applicable (https://github.com/sccn/xdf). The content type is the
                preferred way to find streams (as opposed to searching by name).
        channel_count -- Number of channels per sample. This stays constant for
                         the lifetime of the stream. (default 1)
        nominal_srate -- The sampling rate (in Hz) as advertised by the data
                         source, regular (otherwise set to IRREGULAR_RATE).
                         (default IRREGULAR_RATE)
        channel_format -- Format/type of each channel. If your channels have
                          different formats, consider supplying multiple
                          streams or use the largest type that can hold
                          them all (such as cf_double64). It is also allowed
                          to pass this as a string, without the cf_ prefix,
                          e.g., 'float32' (default cf_float32)
        source_id -- Unique identifier of the device or source of the data, if
                     available (such as the serial number). This is critical
                     for system robustness since it allows recipients to
                     recover from failure even after the serving app, device or
                     computer crashes (just by finding a stream with the same
                     source id on the network again). Therefore, it is highly
                     recommended to always try to provide whatever information
                     can uniquely identify the data source itself.
                     (default '')

        """
        if handle is not None:
            self.obj = c_void_p(handle)
        else:
            if isinstance(channel_format, str):
                channel_format = string2fmt[channel_format]
            self.obj = lib.lsl_create_streaminfo(
                c_char_p(str.encode(name)),
                c_char_p(str.encode(type)),
                channel_count,
                c_double(nominal_srate),
                channel_format,
                c_char_p(str.encode(source_id)),
            )
            self.obj = c_void_p(self.obj)
            if not self.obj:
                raise RuntimeError("could not create stream description " "object.")

    def __del__(self):
        """Destroy a previously created StreamInfo object."""
        # noinspection PyBroadException
        try:
            lib.lsl_destroy_streaminfo(self.obj)
        except:
            pass

    # === Core Information (assigned at construction) ===

    def name(self):
        """Name of the stream.

        This is a human-readable name. For streams offered by device modules,
        it refers to the type of device or product series that is generating
        the data of the stream. If the source is an application, the name may
        be a more generic or specific identifier. Multiple streams with the
        same name can coexist, though potentially at the cost of ambiguity (for
        the recording app or experimenter).

        """
        return lib.lsl_get_name(self.obj).decode("utf-8")

    def type(self):
        """Content type of the stream.

        The content type is a short string such as "EEG", "Gaze" which
        describes the content carried by the channel (if known). If a stream
        contains mixed content this value need not be assigned but may instead
        be stored in the description of channel types. To be useful to
        applications and automated processing systems using the recommended
        content types is preferred.

        """
        return lib.lsl_get_type(self.obj).decode("utf-8")

    def channel_count(self):
        """Number of channels of the stream.

        A stream has at least one channel; the channel count stays constant for
        all samples.

        """
        return lib.lsl_get_channel_count(self.obj)

    def nominal_srate(self):
        """Sampling rate of the stream, according to the source (in Hz).

        If a stream is irregularly sampled, this should be set to
        IRREGULAR_RATE.

        Note that no data will be lost even if this sampling rate is incorrect
        or if a device has temporary hiccups, since all samples will be
        transmitted anyway (except for those dropped by the device itself).
        However, when the recording is imported into an application, a good
        data importer may correct such errors more accurately if the advertised
        sampling rate was close to the specs of the device.

        """
        return lib.lsl_get_nominal_srate(self.obj)

    def channel_format(self):
        """Channel format of the stream.

        All channels in a stream have the same format. However, a device might
        offer multiple time-synched streams each with its own format.

        """
        return lib.lsl_get_channel_format(self.obj)

    def source_id(self):
        """Unique identifier of the stream's source, if available.

        The unique source (or device) identifier is an optional piece of
        information that, if available, allows that endpoints (such as the
        recording program) can re-acquire a stream automatically once it is
        back online.

        """
        return lib.lsl_get_source_id(self.obj).decode("utf-8")

    # === Hosting Information (assigned when bound to an outlet/inlet) ===

    def version(self):
        """Protocol version used to deliver the stream."""
        return lib.lsl_get_version(self.obj)

    def created_at(self):
        """Creation time stamp of the stream.

        This is the time stamp when the stream was first created
        (as determined via local_clock() on the providing machine).

        """
        return lib.lsl_get_created_at(self.obj)

    def uid(self):
        """Unique ID of the stream outlet instance (once assigned).

        This is a unique identifier of the stream outlet, and is guaranteed to
        be different across multiple instantiations of the same outlet (e.g.,
        after a re-start).

        """
        return lib.lsl_get_uid(self.obj).decode("utf-8")

    def session_id(self):
        """Session ID for the given stream.

        The session id is an optional human-assigned identifier of the
        recording session. While it is rarely used, it can be used to prevent
        concurrent recording activities on the same sub-network (e.g., in
        multiple experiment areas) from seeing each other's streams
        (can be assigned in a configuration file read by liblsl, see also
        Network Connectivity in the LSL wiki).

        """
        return lib.lsl_get_session_id(self.obj).decode("utf-8")

    def hostname(self):
        """Hostname of the providing machine."""
        return lib.lsl_get_hostname(self.obj).decode("utf-8")

    # === Data Description (can be modified) ===
    def desc(self):
        """Extended description of the stream.

        It is highly recommended that at least the channel labels are described
        here. See code examples on the LSL wiki. Other information, such
        as amplifier settings, measurement units if deviating from defaults,
        setup information, subject information, etc., can be specified here, as
        well. Meta-data recommendations follow the XDF file format project
        (github.com/sccn/xdf/wiki/Meta-Data or web search for: XDF meta-data).

        Important: if you use a stream content type for which meta-data
        recommendations exist, please try to lay out your meta-data in
        agreement with these recommendations for compatibility with other
        applications.

        """
        return XMLElement(lib.lsl_get_desc(self.obj))

    def as_xml(self):
        """Retrieve the entire stream_info in XML format.

        This yields an XML document (in string form) whose top-level element is
        <description>. The description element contains one element for each
        field of the stream_info class, including:
        a) the core elements <name>, <type>, <channel_count>, <nominal_srate>,
           <channel_format>, <source_id>
        b) the misc elements <version>, <created_at>, <uid>, <session_id>,
           <v4address>, <v4data_port>, <v4service_port>, <v6address>,
           <v6data_port>, <v6service_port>
        c) the extended description element <desc> with user-defined
           sub-elements.

        """
        return lib.lsl_get_xml(self.obj).decode("utf-8")

    def get_channel_labels(self):
        """Get the channel names in the description.

        Returns
        -------
        labels : list of str or ``None`` | None
            List of channel names, matching the number of total channels.
            If ``None``, the channel names are not set.

            .. warning::

                If a list of str and ``None`` are returned, some of the channel names
                are missing. This is not expected and could occur if the XML tree in
                the ``desc`` property is tempered with outside of the defined getter and
                setter.
        """
        return self._get_channel_info("label")

    def get_channel_types(self):
        """Get the channel types in the description.

        Returns
        -------
        types : list of str or ``None`` | None
            List of channel types, matching the number of total channels.
            If ``None``, the channel types are not set.

            .. warning::

                If a list of str and ``None`` are returned, some of the channel types
                are missing. This is not expected and could occur if the XML tree in
                the ``desc`` property is tempered with outside of the defined getter and
                setter.
        """
        return self._get_channel_info("type")

    def get_channel_units(self):
        """Get the channel units in the description.

        Returns
        -------
        units : list of str or ``None`` | None
            List of channel units, matching the number of total channels.
            If ``None``, the channel units are not set.

            .. warning::

                If a list of str and ``None`` are returned, some of the channel units
                are missing. This is not expected and could occur if the XML tree in
                the ``desc`` property is tempered with outside of the defined getter and
                setter.
        """
        return self._get_channel_info("unit")

    def _get_channel_info(self, name):
        """Get the 'channel/name' element in the XML tree."""
        if self.desc().child("channels").empty():
            return None
        ch_infos = list()
        channels = self.desc().child("channels")
        ch = channels.child("channel")
        while not ch.empty():
            ch_info = ch.child(name).first_child().value()
            if len(ch_info) != 0:
                ch_infos.append(ch_info)
            else:
                ch_infos.append(None)
            ch = ch.next_sibling()
        if all(ch_info is None for ch_info in ch_infos):
            return None
        if len(ch_infos) != self.channel_count():
            print(
                f"The stream description contains {len(ch_infos)} elements for "
                f"{self.channel_count()} channels.",
            )
        return ch_infos

    def set_channel_labels(self, labels):
        """Set the channel names in the description. Existing labels are overwritten.

        Parameters
        ----------
        labels : list of str
            List of channel names, matching the number of total channels.
        """
        self._set_channel_info(labels, "label")

    def set_channel_types(self, types):
        """Set the channel types in the description. Existing types are overwritten.

        The types are given as human readable strings, e.g. ``'eeg'``.

        Parameters
        ----------
        types : list of str | str
            List of channel types, matching the number of total channels.
            If a single `str` is provided, the type is applied to all channels.
        """
        types = [types] * self.channel_count() if isinstance(types, str) else types
        self._set_channel_info(types, "type")

    def set_channel_units(self, units):
        """Set the channel units in the description. Existing units are overwritten.

        The units are given as human readable strings, e.g. ``'microvolts'``, or as
        multiplication factor, e.g. ``-6`` for ``1e-6`` thus converting e.g. Volts to
        microvolts.

        Parameters
        ----------
        units : list of str | list of int | array of int | str | int
            List of channel units, matching the number of total channels.
            If a single `str` or `int` is provided, the unit is applied to all channels.

        Notes
        -----
        Some channel types do not have a unit. The `str` ``none`` or the `int` 0 should
        be used to denote this channel unit, corresponding to ``FIFF_UNITM_NONE`` in
        MNE-Python.
        """
        if isinstance(units, (int, str)):
            units = [units] * self.channel_count()
        else:  # iterable
            units = [
                str(int(unit)) if isinstance(unit, int) else unit for unit in units
            ]
        self._set_channel_info(units, "unit")

    def _set_channel_info(self, ch_infos, name) -> None:
        """Set the 'channel/name' element in the XML tree."""
        if len(ch_infos) != self.channel_count():
            raise ValueError(
                f"The number of provided channel {name} {len(ch_infos)} "
                f"must match the number of channels {self.channel_count()}."
            )

        channels = StreamInfo._add_first_node(self.desc, "channels")
        # fill the 'channel/name' element of the tree and overwrite existing values
        ch = channels.child("channel")
        for ch_info in ch_infos:
            ch = channels.append_child("channel") if ch.empty() else ch
            StreamInfo._set_description_node(ch, {name: ch_info})
            ch = ch.next_sibling()
        StreamInfo._prune_description_node(ch, channels)

    # -- Helper methods to interact with the XMLElement tree ---------------------------
    @staticmethod
    def _add_first_node(desc, name):
        """Add the first node in the description and return it."""
        if desc().child(name).empty():
            node = desc().append_child(name)
        else:
            node = desc().child(name)
        return node

    @staticmethod
    def _prune_description_node(node, parent):
        """Prune a node and remove outdated entries."""
        # this is useful in case the sinfo is tempered with and had more entries of type
        # 'node' than it should.
        while not node.empty():
            node_next = node.next_sibling()
            parent.remove_child(node)
            node = node_next

    @staticmethod
    def _set_description_node(node, mapping):
        """Set the key: value child(s) of a node."""
        for key, value in mapping.items():
            value = str(int(value)) if isinstance(value, int) else str(value)
            if node.child(key).empty():
                node.append_child_value(key, value)
            else:
                node.child(key).first_child().set_value(value)


# =====================
# === Stream Outlet ===
# =====================


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
        self.obj = c_void_p(self.obj)
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
        except:
            pass

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
            if self.channel_format == ChannelValueFormats.STRING.value:
                x = [v.encode("utf-8") for v in x]
            handle_error(
                self.do_push_sample(
                    self.obj,
                    self.sample_type(*x),
                    c_double(timestamp),
                    c_int(pushthrough),
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
            timestamp_c = c_double(timestamp)
            # Select the corresponding push_chunk method
            liblsl_push_chunk_func = self.do_push_chunk
        except TypeError:
            try:
                timestamp_c = (c_double * len(timestamp))(*timestamp)
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
                    c_long(n_values),
                    timestamp_c,
                    c_int(pushthrough),
                )
            )
        except TypeError:
            # don't send empty chunks
            if len(x):
                if type(x[0]) is list:
                    x = [v for sample in x for v in sample]
                if self.channel_format == ChannelValueFormats.STRING.value:
                    x = [v.encode("utf-8") for v in x]
                if len(x) % self.channel_count == 0:
                    # x is a flattened list of multiplexed values
                    constructor = self.value_type * len(x)
                    # noinspection PyCallingNonCallable
                    handle_error(
                        liblsl_push_chunk_func(
                            self.obj,
                            constructor(*x),
                            c_long(len(x)),
                            timestamp_c,
                            c_int(pushthrough),
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
        return bool(lib.lsl_wait_for_consumers(self.obj, c_double(timeout)))

    def get_info(self):
        outlet_info = lib.lsl_get_info(self.obj)
        return StreamInfo(handle=outlet_info)


# =========================
# === Resolve Functions ===
# =========================


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
    buffer = (c_void_p * 1024)()
    num_found = lib.lsl_resolve_all(byref(buffer), 1024, c_double(wait_time))
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
    buffer = (c_void_p * 1024)()
    num_found = lib.lsl_resolve_byprop(
        byref(buffer),
        1024,
        c_char_p(str.encode(prop)),
        c_char_p(str.encode(value)),
        minimum,
        c_double(timeout),
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
    buffer = (c_void_p * 1024)()
    num_found = lib.lsl_resolve_bypred(
        byref(buffer), 1024, c_char_p(str.encode(predicate)), minimum, c_double(timeout)
    )
    return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


# ====================
# === Memory functions
# ====================
def free_char_p_array_memory(char_p_array, num_elements):
    pointers = cast(char_p_array, POINTER(c_void_p))
    for p in range(num_elements):
        if pointers[p] is not None:  # only free initialized pointers
            lib.lsl_destroy_string(pointers[p])


# ====================
# === Stream Inlet ===
# ====================


class StreamInlet:
    """A stream inlet.

    Inlets are used to receive streaming data (and meta-data) from the lab
    network.

    """

    def __init__(
            self, info, max_buflen=360, max_chunklen=0, recover=True, processing_flags=PostProcessingFlags.NONE.value
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
        self.obj = c_void_p(self.obj)
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
        errcode = c_int()
        result = lib.lsl_get_fullinfo(self.obj, c_double(timeout), byref(errcode))
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
        errcode = c_int()
        lib.lsl_open_stream(self.obj, c_double(timeout), byref(errcode))
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
        errcode = c_int()
        result = lib.lsl_time_correction(self.obj, c_double(timeout), byref(errcode))
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

        errcode = c_int()
        timestamp = self.do_pull_sample(
            self.obj,
            byref(self.sample),
            self.channel_count,
            c_double(timeout),
            byref(errcode),
        )
        handle_error(errcode)
        if timestamp:
            sample = [v for v in self.sample]
            if self.channel_format == ChannelValueFormats.STRING.value:
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
                (c_double * max_samples)(),
            )
        if dest_obj is not None:
            data_buff = (self.value_type * max_values).from_buffer(dest_obj)
        else:
            data_buff = self.buffers[max_samples][0]
        ts_buff = self.buffers[max_samples][1]

        # read data into it
        errcode = c_int()
        # noinspection PyCallingNonCallable
        num_elements = self.do_pull_chunk(
            self.obj,
            byref(data_buff),
            byref(ts_buff),
            c_size_t(max_values),
            c_size_t(max_samples),
            c_double(timeout),
            byref(errcode),
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
            if self.channel_format == ChannelValueFormats.STRING.value:
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


# ===================
# === XML Element ===
# ===================


class XMLElement:
    """A lightweight XML element tree modeling the .desc() field of StreamInfo.

    Has a name and can have multiple named children or have text content as
    value; attributes are omitted. Insider note: The interface is modeled after
    a subset of pugixml's node type and is compatible with it. See also
    http://pugixml.googlecode.com/svn/tags/latest/docs/manual/access.html for
    additional documentation.

    """

    def __init__(self, handle):
        """Construct new XML element from existing handle."""
        self.e = c_void_p(handle)

    # === Tree Navigation ===

    def first_child(self):
        """Get the first child of the element."""
        return XMLElement(lib.lsl_first_child(self.e))

    def last_child(self):
        """Get the last child of the element."""
        return XMLElement(lib.lsl_last_child(self.e))

    def child(self, name):
        """Get a child with a specified name."""
        return XMLElement(lib.lsl_child(self.e, str.encode(name)))

    def next_sibling(self, name=None):
        """Get the next sibling in the children list of the parent node.

        If a name is provided, the next sibling with the given name is returned.

        """
        if name is None:
            return XMLElement(lib.lsl_next_sibling(self.e))
        else:
            return XMLElement(lib.lsl_next_sibling_n(self.e, str.encode(name)))

    def previous_sibling(self, name=None):
        """Get the previous sibling in the children list of the parent node.

        If a name is provided, the previous sibling with the given name is
        returned.

        """
        if name is None:
            return XMLElement(lib.lsl_previous_sibling(self.e))
        else:
            return XMLElement(lib.lsl_previous_sibling_n(self.e, str.encode(name)))

    def parent(self):
        """Get the parent node."""
        return XMLElement(lib.lsl_parent(self.e))

    # === Content Queries ===

    def empty(self):
        """Whether this node is empty."""
        return bool(lib.lsl_empty(self.e))

    def is_text(self):
        """Whether this is a text body (instead of an XML element).

        True both for plain char data and CData.

        """
        return bool(lib.lsl_is_text(self.e))

    def name(self):
        """Name of the element."""
        return lib.lsl_name(self.e).decode("utf-8")

    def value(self):
        """Value of the element."""
        return lib.lsl_value(self.e).decode("utf-8")

    def child_value(self, name=None):
        """Get child value (value of the first child that is text).

        If a name is provided, then the value of the first child with the
        given name is returned.

        """
        if name is None:
            res = lib.lsl_child_value(self.e)
        else:
            res = lib.lsl_child_value_n(self.e, str.encode(name))
        return res.decode("utf-8")

    # === Modification ===

    def append_child_value(self, name, value):
        """Append a child node with a given name, which has a (nameless)
        plain-text child with the given text value."""
        return XMLElement(
            lib.lsl_append_child_value(self.e, str.encode(name), str.encode(value))
        )

    def prepend_child_value(self, name, value):
        """Prepend a child node with a given name, which has a (nameless)
        plain-text child with the given text value."""
        return XMLElement(
            lib.lsl_prepend_child_value(self.e, str.encode(name), str.encode(value))
        )

    def set_child_value(self, name, value):
        """Set the text value of the (nameless) plain-text child of a named
        child node."""
        return XMLElement(
            lib.lsl_set_child_value(self.e, str.encode(name), str.encode(value))
        )

    def set_name(self, name):
        """Set the element's name. Returns False if the node is empty."""
        return bool(lib.lsl_set_name(self.e, str.encode(name)))

    def set_value(self, value):
        """Set the element's value. Returns False if the node is empty."""
        return bool(lib.lsl_set_value(self.e, str.encode(value)))

    def append_child(self, name):
        """Append a child element with the specified name."""
        return XMLElement(lib.lsl_append_child(self.e, str.encode(name)))

    def prepend_child(self, name):
        """Prepend a child element with the specified name."""
        return XMLElement(lib.lsl_prepend_child(self.e, str.encode(name)))

    def append_copy(self, elem):
        """Append a copy of the specified element as a child."""
        return XMLElement(lib.lsl_append_copy(self.e, elem.e))

    def prepend_copy(self, elem):
        """Prepend a copy of the specified element as a child."""
        return XMLElement(lib.lsl_prepend_copy(self.e, elem.e))

    def remove_child(self, rhs):
        """Remove a given child element, specified by name or as element."""
        if type(rhs) is XMLElement:
            lib.lsl_remove_child(self.e, rhs.e)
        else:
            lib.lsl_remove_child_n(self.e, rhs)


# ==========================
# === ContinuousResolver ===
# ==========================


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
                str.encode(pred), c_double(forget_after)
            )
        elif prop is not None and value is not None:
            self.obj = lib.lsl_create_continuous_resolver_byprop(
                str.encode(prop), str.encode(value), c_double(forget_after)
            )
        elif prop is not None or value is not None:
            raise ValueError(
                "if prop is specified, then value must be "
                "specified, too, and vice versa."
            )
        else:
            self.obj = lib.lsl_create_continuous_resolver(c_double(forget_after))
        self.obj = c_void_p(self.obj)
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
        buffer = (c_void_p * 1024)()
        num_found = lib.lsl_resolver_results(self.obj, byref(buffer), 1024)
        return [StreamInfo(handle=buffer[k]) for k in range(num_found)]


# =========================
# === Error Definitions ===
# =========================


# noinspection PyShadowingBuiltins
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
    if type(errcode) is c_int:
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


# =================================================
# === Compatibility Interface for old pylsl API ===
# =================================================

# set class aliases
stream_info = StreamInfo
stream_outlet = StreamOutlet
stream_inlet = StreamInlet
xml_element = XMLElement
timeout_error = TimeoutError
lost_error = LostError
vectorf = vectord = vectorl = vectori = vectors = vectorc = vectorstr = list

# Recommended to use the ChannelValueFormats Enum class
cf_float32 = 1
cf_double64 = 2
cf_string = 3
cf_int32 = 4
cf_int16 = 5
cf_int8 = 6
cf_int64 = 7
cf_undefined = 0

# Recommended to use the PostProcessingFlags Enum class
proc_none = 0
proc_clocksync = 1
proc_dejitter = 2
proc_monotonize = 4
proc_threadsafe = 8
proc_ALL = (proc_none | proc_clocksync | proc_dejitter | proc_monotonize | proc_threadsafe)


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


# ==================================
# === Module Initialization Code ===
# ==================================


def find_liblsl_libraries(verbose=False):
    """finds the binary lsl library.

    Search order is to first try to use the path stored in the environment
    variable PYLSL_LIB (if available), then search through the package
    directory, and finally search the whole system.

    returns
    -------

    path: Generator[str]
        a generator yielding possible paths to the library

    """
    # find and load library
    if "PYLSL_LIB" in os.environ:
        path = os.environ["PYLSL_LIB"]
        if os.path.isfile(path):
            yield path
        elif verbose:
            print(
                "Skipping PYLSL_LIB:",
                path,
                " because it was either not " + "found or is not a valid file",
            )

    os_name = platform.system()
    if os_name in ["Windows", "Microsoft"]:
        libsuffix = ".dll"
    elif os_name == "Darwin":
        libsuffix = ".dylib"
    elif os_name == "Linux":
        libsuffix = ".so"
    else:
        raise RuntimeError("unrecognized operating system:", os_name)

    libbasepath = os.path.join(os.path.dirname(__file__), "lib")

    # because there were quite a few errors with pickung up old binaries
    # still lurking in the system or environment, we first search through all
    # prefix/suffix/bitness variants in the package itself, i.e. in libbasepath
    # before searching through the system with util.find_library
    for scope in ["package", "system"]:
        for libprefix in ["", "lib"]:
            for debugsuffix in ["", "-debug"]:
                for bitness in ["", str(8 * struct.calcsize("P"))]:
                    if scope == "package":
                        path = os.path.join(
                            libbasepath,
                            libprefix + "lsl" + bitness + debugsuffix + libsuffix,
                        )
                        if os.path.isfile(path):
                            yield path
                    elif (scope == "system") and os_name not in [
                        "Windows",
                        "Microsoft",
                    ]:
                        # according to docs:
                        # On Linux, find_library tries to run external
                        # programs (/sbin/ldconfig, gcc, and objdump) to find
                        # the library file
                        # On OS X, find_library tries several predefined
                        # naming schemes and paths to locate the library,
                        # On Windows, find_library searches along the system
                        # search path. However, we disallow finding system-level
                        # lsl.dll on Windows because it causes too many problems
                        # and should never be necessary.
                        quallibname = libprefix + "lsl" + bitness + debugsuffix
                        path = util.find_library(quallibname)
                        if path is None and os_name == "Darwin":
                            # MacOS >= 10.15 requires only searches 1 or 2 paths, thus requires the full lib path
                            # https://bugs.python.org/issue43964#msg394782
                            # Here we try the default homebrew folder, but you may have installed it elsewhere,
                            #  in which case you'd use the DYLD_LIBRARY_PATH (see error message below)".
                            path = util.find_library("/opt/homebrew/lib/" + quallibname)
                        if path is not None:
                            yield path


__dload_msg = (
    "You can install the LSL library with conda: `conda install -c conda-forge liblsl`"
)
if platform.system() == "Darwin":
    __dload_msg += "\nor with homebrew: `brew install labstreaminglayer/tap/lsl`"
__dload_msg += (
    "\nor otherwise download it from the liblsl releases page assets: "
    "https://github.com/sccn/liblsl/releases"
)
if platform.system() == "Darwin":
    # https://bugs.python.org/issue43964#msg394782
    __dload_msg += (
        "\nOn modern MacOS (>= 10.15) it is further necessary to set the DYLD_LIBRARY_PATH "
        "environment variable. e.g. `>DYLD_LIBRARY_PATH=/opt/homebrew/lib python path/to/my_lsl_script.py`"
    )


try:
    libpath = next(find_liblsl_libraries())
    lib = CDLL(libpath)
except StopIteration:
    err_msg = (
        "LSL binary library file was not found. Please make sure that the "
        + "binary file can be found in the package lib folder\n ("
        + os.path.join(os.path.dirname(__file__), "lib")
        + ")\n or "
    )
    if platform.system() not in ["Windows", "Microsoft"]:
        err_msg += "the system search path. Alternatively, "
    err_msg += "specify the PYLSL_LIB environment variable.\n "
    raise RuntimeError(err_msg + __dload_msg)
except OSError:
    err_msg = "liblsl library '" + libpath + "' found but could not be loaded "
    err_msg += "- possible platform/architecture mismatch.\n "
    if platform.system() in ["Windows", "Microsoft"]:
        err_msg += "You may need to download and install the latest Microsoft Visual C++ Redistributable."
    raise RuntimeError(err_msg + "\n " + __dload_msg)


# set function return types where necessary
lib.lsl_local_clock.restype = c_double
lib.lsl_create_streaminfo.restype = c_void_p
lib.lsl_library_info.restype = c_char_p
lib.lsl_get_name.restype = c_char_p
lib.lsl_get_type.restype = c_char_p
lib.lsl_get_nominal_srate.restype = c_double
lib.lsl_get_source_id.restype = c_char_p
lib.lsl_get_created_at.restype = c_double
lib.lsl_get_uid.restype = c_char_p
lib.lsl_get_session_id.restype = c_char_p
lib.lsl_get_hostname.restype = c_char_p
lib.lsl_get_desc.restype = c_void_p
lib.lsl_get_xml.restype = c_char_p
lib.lsl_create_outlet.restype = c_void_p
lib.lsl_create_inlet.restype = c_void_p
lib.lsl_get_fullinfo.restype = c_void_p
lib.lsl_get_info.restype = c_void_p
lib.lsl_open_stream.restype = c_void_p
lib.lsl_time_correction.restype = c_double
lib.lsl_pull_sample_f.restype = c_double
lib.lsl_pull_sample_d.restype = c_double
lib.lsl_pull_sample_l.restype = c_double
lib.lsl_pull_sample_i.restype = c_double
lib.lsl_pull_sample_s.restype = c_double
lib.lsl_pull_sample_c.restype = c_double
lib.lsl_pull_sample_str.restype = c_double
lib.lsl_pull_sample_buf.restype = c_double
lib.lsl_first_child.restype = c_void_p
lib.lsl_first_child.argtypes = [
    c_void_p,
]
lib.lsl_last_child.restype = c_void_p
lib.lsl_last_child.argtypes = [
    c_void_p,
]
lib.lsl_next_sibling.restype = c_void_p
lib.lsl_next_sibling.argtypes = [
    c_void_p,
]
lib.lsl_previous_sibling.restype = c_void_p
lib.lsl_previous_sibling.argtypes = [
    c_void_p,
]
lib.lsl_parent.restype = c_void_p
lib.lsl_parent.argtypes = [
    c_void_p,
]
lib.lsl_child.restype = c_void_p
lib.lsl_child.argtypes = [c_void_p, c_char_p]
lib.lsl_next_sibling_n.restype = c_void_p
lib.lsl_next_sibling_n.argtypes = [c_void_p, c_char_p]
lib.lsl_previous_sibling_n.restype = c_void_p
lib.lsl_previous_sibling_n.argtypes = [c_void_p, c_char_p]
lib.lsl_name.restype = c_char_p
lib.lsl_name.argtypes = [
    c_void_p,
]
lib.lsl_value.restype = c_char_p
lib.lsl_value.argtypes = [
    c_void_p,
]
lib.lsl_child_value.restype = c_char_p
lib.lsl_child_value.argtypes = [
    c_void_p,
]
lib.lsl_child_value_n.restype = c_char_p
lib.lsl_child_value_n.argtypes = [c_void_p, c_char_p]
lib.lsl_append_child_value.restype = c_void_p
lib.lsl_append_child_value.argtypes = [c_void_p, c_char_p, c_char_p]
lib.lsl_prepend_child_value.restype = c_void_p
lib.lsl_prepend_child_value.argtypes = [c_void_p, c_char_p, c_char_p]
# Return type for lsl_set_child_value, lsl_set_name, lsl_set_value is int
lib.lsl_set_child_value.argtypes = [c_void_p, c_char_p, c_char_p]
lib.lsl_set_name.argtypes = [c_void_p, c_char_p]
lib.lsl_set_value.argtypes = [c_void_p, c_char_p]
lib.lsl_append_child.restype = c_void_p
lib.lsl_append_child.argtypes = [c_void_p, c_char_p]
lib.lsl_prepend_child.restype = c_void_p
lib.lsl_prepend_child.argtypes = [c_void_p, c_char_p]
lib.lsl_append_copy.restype = c_void_p
lib.lsl_append_copy.argtypes = [c_void_p, c_void_p]
lib.lsl_prepend_copy.restype = c_void_p
lib.lsl_prepend_copy.argtypes = [c_void_p, c_void_p]
lib.lsl_remove_child_n.argtypes = [c_void_p, c_char_p]
lib.lsl_remove_child.argtypes = [c_void_p, c_void_p]
lib.lsl_destroy_string.argtypes = [c_void_p]
# noinspection PyBroadException
try:
    lib.lsl_pull_chunk_f.restype = c_long
    lib.lsl_pull_chunk_d.restype = c_long
    lib.lsl_pull_chunk_l.restype = c_long
    lib.lsl_pull_chunk_i.restype = c_long
    lib.lsl_pull_chunk_s.restype = c_long
    lib.lsl_pull_chunk_c.restype = c_long
    lib.lsl_pull_chunk_str.restype = c_long
    lib.lsl_pull_chunk_buf.restype = c_long
except Exception:
    print("pylsl: chunk transfer functions not available in your liblsl " "version.")
# noinspection PyBroadException
try:
    lib.lsl_create_continuous_resolver.restype = c_void_p
    lib.lsl_create_continuous_resolver_bypred.restype = c_void_p
    lib.lsl_create_continuous_resolver_byprop.restype = c_void_p
except Exception:
    print("pylsl: ContinuousResolver not (fully) available in your liblsl " "version.")


# int64 support on windows and 32bit OSes isn't there yet
if struct.calcsize("P") != 4 and platform.system() != "Windows":
    push_sample_int64 = lib.lsl_push_sample_ltp
    pull_sample_int64 = lib.lsl_pull_sample_l
    push_chunk_int64 = lib.lsl_push_chunk_ltp
    push_chunk_int64_n = lib.lsl_push_chunk_ltnp
    pull_chunk_int64 = lib.lsl_pull_chunk_l
else:

    def push_sample_int64(*_):
        raise NotImplementedError("int64 support isn't enabled on your platform")

    pull_sample_int64 = push_sample_int64
    push_chunk_int64 = push_sample_int64
    push_chunk_int64_n = push_sample_int64
    pull_chunk_int64 = push_sample_int64

# set up some type maps
string2fmt = {
    "float32": cf_float32,
    "double64": cf_double64,
    "string": cf_string,
    "int32": cf_int32,
    "int16": cf_int16,
    "int8": cf_int8,
    "int64": cf_int64,
}
fmt2string = [
    "undefined",
    "float32",
    "double64",
    "string",
    "int32",
    "int16",
    "int8",
    "int64",
]
fmt2type = [[], c_float, c_double, c_char_p, c_int, c_short, c_byte, c_longlong]
fmt2push_sample = [
    [],
    lib.lsl_push_sample_ftp,
    lib.lsl_push_sample_dtp,
    lib.lsl_push_sample_strtp,
    lib.lsl_push_sample_itp,
    lib.lsl_push_sample_stp,
    lib.lsl_push_sample_ctp,
    push_sample_int64,
]
fmt2pull_sample = [
    [],
    lib.lsl_pull_sample_f,
    lib.lsl_pull_sample_d,
    lib.lsl_pull_sample_str,
    lib.lsl_pull_sample_i,
    lib.lsl_pull_sample_s,
    lib.lsl_pull_sample_c,
    pull_sample_int64,
]
# noinspection PyBroadException
try:
    fmt2push_chunk = [
        [],
        lib.lsl_push_chunk_ftp,
        lib.lsl_push_chunk_dtp,
        lib.lsl_push_chunk_strtp,
        lib.lsl_push_chunk_itp,
        lib.lsl_push_chunk_stp,
        lib.lsl_push_chunk_ctp,
        push_chunk_int64,
    ]
    fmt2push_chunk_n = [
        [],
        lib.lsl_push_chunk_ftnp,
        lib.lsl_push_chunk_dtnp,
        lib.lsl_push_chunk_strtnp,
        lib.lsl_push_chunk_itnp,
        lib.lsl_push_chunk_stnp,
        lib.lsl_push_chunk_ctnp,
        push_chunk_int64_n,
    ]
    fmt2pull_chunk = [
        [],
        lib.lsl_pull_chunk_f,
        lib.lsl_pull_chunk_d,
        lib.lsl_pull_chunk_str,
        lib.lsl_pull_chunk_i,
        lib.lsl_pull_chunk_s,
        lib.lsl_pull_chunk_c,
        pull_chunk_int64,
    ]
except Exception:
    # if not available
    fmt2push_chunk = [None] * len(fmt2string)
    fmt2push_chunk_n = [None] * len(fmt2string)
    fmt2pull_chunk = [None] * len(fmt2string)
