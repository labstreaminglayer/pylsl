import ctypes

from .lib import lib, string2fmt, cf_float32
from .util import IRREGULAR_RATE


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
        channel_format=cf_float32,
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
            self.obj = ctypes.c_void_p(handle)
        else:
            if isinstance(channel_format, str):
                channel_format = string2fmt[channel_format]
            self.obj = lib.lsl_create_streaminfo(
                ctypes.c_char_p(str.encode(name)),
                ctypes.c_char_p(str.encode(type)),
                channel_count,
                ctypes.c_double(nominal_srate),
                channel_format,
                ctypes.c_char_p(str.encode(source_id)),
            )
            self.obj = ctypes.c_void_p(self.obj)
            if not self.obj:
                raise RuntimeError("could not create stream description " "object.")

    def __del__(self):
        """Destroy a previously created StreamInfo object."""
        # noinspection PyBroadException
        try:
            lib.lsl_destroy_streaminfo(self.obj)
        except Exception as e:
            print(f"StreamInfo deletion triggered error: {e}")

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
        self.e = ctypes.c_void_p(handle)

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
