import ctypes
import ctypes.util
import os
import platform
import struct


# For up to 24-bit precision measurements in the appropriate physical unit (
# e.g., microvolts). Integers from -16777216 to 16777216 are represented
# accurately.
cf_float32 = 1
# For universal numeric data as long as permitted by network and disk budget.
#  The largest representable integer is 53-bit.
cf_double64 = 2
# For variable-length ASCII strings or data blobs, such as video frames,
# complex event descriptions, etc.
cf_string = 3
# For high-rate digitized formats that require 32-bit precision. Depends
# critically on meta-data to represent meaningful units. Useful for
# application event codes or other coded data.
cf_int32 = 4
# For very high bandwidth signals or CD quality audio (for professional audio
#  float is recommended).
cf_int16 = 5
# For binary signals or other coded data.
cf_int8 = 6
# For now only for future compatibility. Support for this type is not
# available on all languages and platforms.
cf_int64 = 7
# Can not be transmitted.
cf_undefined = 0


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

    libbasepath = os.path.dirname(__file__)

    # because there were quite a few errors with picking up old binaries
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
                        path = ctypes.util.find_library(quallibname)
                        if path is None and os_name == "Darwin":
                            # MacOS >= 10.15 requires only searches 1 or 2 paths, thus requires the full lib path
                            # https://bugs.python.org/issue43964#msg394782
                            # Here we try the default homebrew folder, but you may have installed it elsewhere,
                            #  in which case you'd use the DYLD_LIBRARY_PATH (see error message below)".
                            path = ctypes.util.find_library(
                                "/opt/homebrew/lib/" + quallibname
                            )
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
    lib = ctypes.CDLL(libpath)
except StopIteration:
    err_msg = (
        "LSL binary library file was not found. Please make sure that the "
        + "binary file can be found in the package lib folder\n ("
        + os.path.dirname(__file__)
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
lib.lsl_local_clock.restype = ctypes.c_double
lib.lsl_create_streaminfo.restype = ctypes.c_void_p
lib.lsl_library_info.restype = ctypes.c_char_p
lib.lsl_get_name.restype = ctypes.c_char_p
lib.lsl_get_type.restype = ctypes.c_char_p
lib.lsl_get_nominal_srate.restype = ctypes.c_double
lib.lsl_get_source_id.restype = ctypes.c_char_p
lib.lsl_get_created_at.restype = ctypes.c_double
lib.lsl_get_uid.restype = ctypes.c_char_p
lib.lsl_get_session_id.restype = ctypes.c_char_p
lib.lsl_get_hostname.restype = ctypes.c_char_p
lib.lsl_get_desc.restype = ctypes.c_void_p
lib.lsl_get_xml.restype = ctypes.c_char_p
lib.lsl_create_outlet.restype = ctypes.c_void_p
lib.lsl_create_inlet.restype = ctypes.c_void_p
lib.lsl_get_fullinfo.restype = ctypes.c_void_p
lib.lsl_get_info.restype = ctypes.c_void_p
lib.lsl_open_stream.restype = ctypes.c_void_p
lib.lsl_time_correction.restype = ctypes.c_double
lib.lsl_pull_sample_f.restype = ctypes.c_double
lib.lsl_pull_sample_d.restype = ctypes.c_double
lib.lsl_pull_sample_l.restype = ctypes.c_double
lib.lsl_pull_sample_i.restype = ctypes.c_double
lib.lsl_pull_sample_s.restype = ctypes.c_double
lib.lsl_pull_sample_c.restype = ctypes.c_double
lib.lsl_pull_sample_str.restype = ctypes.c_double
lib.lsl_pull_sample_buf.restype = ctypes.c_double
lib.lsl_first_child.restype = ctypes.c_void_p
lib.lsl_first_child.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_last_child.restype = ctypes.c_void_p
lib.lsl_last_child.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_next_sibling.restype = ctypes.c_void_p
lib.lsl_next_sibling.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_previous_sibling.restype = ctypes.c_void_p
lib.lsl_previous_sibling.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_parent.restype = ctypes.c_void_p
lib.lsl_parent.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_child.restype = ctypes.c_void_p
lib.lsl_child.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_next_sibling_n.restype = ctypes.c_void_p
lib.lsl_next_sibling_n.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_previous_sibling_n.restype = ctypes.c_void_p
lib.lsl_previous_sibling_n.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_name.restype = ctypes.c_char_p
lib.lsl_name.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_value.restype = ctypes.c_char_p
lib.lsl_value.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_child_value.restype = ctypes.c_char_p
lib.lsl_child_value.argtypes = [
    ctypes.c_void_p,
]
lib.lsl_child_value_n.restype = ctypes.c_char_p
lib.lsl_child_value_n.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_append_child_value.restype = ctypes.c_void_p
lib.lsl_append_child_value.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
]
lib.lsl_prepend_child_value.restype = ctypes.c_void_p
lib.lsl_prepend_child_value.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
]
# Return type for lsl_set_child_value, lsl_set_name, lsl_set_value is int
lib.lsl_set_child_value.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
lib.lsl_set_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_set_value.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_append_child.restype = ctypes.c_void_p
lib.lsl_append_child.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_prepend_child.restype = ctypes.c_void_p
lib.lsl_prepend_child.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_append_copy.restype = ctypes.c_void_p
lib.lsl_append_copy.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.lsl_prepend_copy.restype = ctypes.c_void_p
lib.lsl_prepend_copy.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.lsl_remove_child_n.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.lsl_remove_child.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.lsl_destroy_string.argtypes = [ctypes.c_void_p]
# noinspection PyBroadException
try:
    lib.lsl_pull_chunk_f.restype = ctypes.c_long
    lib.lsl_pull_chunk_d.restype = ctypes.c_long
    lib.lsl_pull_chunk_l.restype = ctypes.c_long
    lib.lsl_pull_chunk_i.restype = ctypes.c_long
    lib.lsl_pull_chunk_s.restype = ctypes.c_long
    lib.lsl_pull_chunk_c.restype = ctypes.c_long
    lib.lsl_pull_chunk_str.restype = ctypes.c_long
    lib.lsl_pull_chunk_buf.restype = ctypes.c_long
except Exception:
    print("pylsl: chunk transfer functions not available in your liblsl " "version.")
# noinspection PyBroadException
try:
    lib.lsl_create_continuous_resolver.restype = ctypes.c_void_p
    lib.lsl_create_continuous_resolver_bypred.restype = ctypes.c_void_p
    lib.lsl_create_continuous_resolver_byprop.restype = ctypes.c_void_p
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
fmt2type = [
    [],
    ctypes.c_float,
    ctypes.c_double,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_short,
    ctypes.c_byte,
    ctypes.c_longlong,
]
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
