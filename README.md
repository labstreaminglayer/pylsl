# pylsl

![publish workflow](https://github.com/labstreaminglayer/pylsl/actions/workflows/publish-to-pypi.yml/badge.svg)
[![PyPI version](https://badge.fury.io/py/pylsl.svg)](https://badge.fury.io/py/pylsl)

This is the Python interface to the [Lab Streaming Layer (LSL)](https://github.com/sccn/labstreaminglayer).
LSL is an overlay network for real-time exchange of time series between applications,
most often used in research environments. LSL has clients for many other languages
and platforms that are compatible with each other.

Let us know if you encounter any bugs (ideally using the issue tracker on
the GitHub project).

# Installation

## Prerequisites

On all non-Windows platforms and for some Windows-Python combinations, you must first obtain a liblsl shared library. See the [liblsl repo documentation](https://github.com/sccn/liblsl) for further details.

## Get pylsl from PyPI

* `pip install pylsl`

## Get pylsl from source

This should only be necessary if you need to modify or debug pylsl.

* Download the pylsl source: `git clone https://github.com/labstreaminglayer/pylsl.git && cd pylsl`
* From the `pylsl` working directory, run `pip install .`.
    * Note: You can use `pip install -e .` to install while keeping the files in-place. This is convenient for developing pylsl.

# Usage

See the examples in src/pylsl/examples. Note that these can be run directly from the commandline with (e.g.) `python -m pylsl.examples.{name-of-example}`.

You can get a list of the examples with `python -c "import pylsl.examples; help(pylsl.examples)"`

## liblsl loading

`pylsl` will search for `liblsl` first at the filepath specified by an environment variable named `PYLSL_LIB`, then in the package directory (default location for Windows), then finally in normal system library folders.

If the shared object is not installed onto a standard search path (or it is but can't be found for some [other bug](https://github.com/labstreaminglayer/pylsl/issues/48)), then we recommend that you copy it to the pylsl installed module path's `lib` subfolder. i.e. `{path/to/env/}site-packages/pylsl/lib`.

* The `site-packages/pylsl` path will only exist _after_ you install `pylsl` in your Python environment.
* You may have to create the `lib` subfolder.
* Use `python -m site` to find the "site-packages" path.
* Use `cp -L` on platforms that use symlinks.

Alternatively, you can use an environment variable. Set the `PYLSL_LIB` environment variable to the location of the library or set `LD_LIBRARY_PATH` to the folder containing the library. For example,

1. `PYLSL_LIB=/usr/local/lib/liblsl.so python -m pylsl.examples.{name-of-example}`, or
2. `LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib python -m pylsl.examples.{name-of-example}`

## Binary data in string streams

LSL's `cf_string` format is really a variable-length blob format ("variable-length
ASCII strings or data blobs, such as video frames" in liblsl's own words), and it
is length-delimited on the network and in XDF files. pylsl treats it that way:

* A `cf_string` outlet accepts `str` (UTF-8 encoded for you) or any bytes-like
  object (`bytes`, `bytearray`, `memoryview`) per channel, sent as is. Values may
  contain NUL bytes.
* A `cf_string` inlet returns decoded `str` by default. With `as_numpy=True`
  (on the inlet or per `pull_chunk` call) it returns the raw bytes of each value
  with no decoding, as a `dtype=object` numpy array.

```python
info = pylsl.StreamInfo("frames", "Video", 1, 0, pylsl.cf_string, "cam0")
outlet = pylsl.StreamOutlet(info)
outlet.push_sample([frame_bytes])

inlet = pylsl.StreamInlet(pylsl.resolve_byprop("name", "frames")[0], as_numpy=True)
sample, ts = inlet.pull_sample()  # sample[0] is the bytes object, unchanged
```

With `as_numpy=True` the values come back as `bytes` inside a `dtype=object`
numpy array, and nothing has been decoded. If a value is text, decode it
yourself; if you want plain Python containers, use `.tolist()`:

```python
sample, ts = inlet.pull_sample()  # 1-D object array, one bytes per channel
text = sample[0].decode("utf-8")  # or "latin-1", or whatever the sender used
blobs = sample.tolist()  # list of bytes

chunk, ts = inlet.pull_chunk()  # 2-D object array (n_samples, n_channels)
first_channel_text = [b.decode("utf-8") for b in chunk[:, 0]]
rows = chunk.tolist()  # list of lists of bytes
```

Decoding is the receiver's decision because only the receiver knows what the
bytes mean. Other LSL clients that read string streams through C-string APIs
will still stop at the first NUL; that is a limitation of those clients, not of
the transport.

## liblsl compatibility

`pylsl` and `liblsl` are versioned independently. Historically they shared version
numbers, but that convention ended after the pylsl 1.17.x series: a pylsl version
number says nothing about which liblsl release it was built against, and in general
you can use the latest pylsl with the latest liblsl.

**Minimum supported liblsl: 1.16.0** (i.e. `pylsl.library_version() >= 116`). pylsl
binds `lsl_create_outlet_ex` unconditionally when it loads the library, and that
function was introduced in liblsl 1.16.0. If an older liblsl is loaded, pylsl emits a
`RuntimeWarning` at import time (it does not raise, in case the subset of the API you
use still works).

Some features require a newer liblsl than the minimum. Where noted, pylsl detects
the capability by looking for the symbol and raises `NotImplementedError` with an
explanatory message if it is absent:

| Feature | Requires |
| --- | --- |
| `StreamOutlet(..., transport_flags=...)` (`lsl_create_outlet_ex`) | liblsl >= 1.16.0 (the pylsl minimum) |
| `transp_sync_blocking` (synchronous zero-copy pushes) | liblsl >= 1.18.0 |
| `pylsl.set_config_filename()` / `pylsl.set_config_content()` | liblsl >= 1.17.7 |
| `StreamInfo.reset_uid()` | liblsl >= 1.18.0 |
| Bulk string free after string-stream pulls (`lsl_destroy_string_array`) | liblsl >= 1.18.0.b4; older liblsl falls back to one `lsl_destroy_string` call per string (slower, same result) |
| `ContinuousResolver`, chunk transfer (`push_chunk`/`pull_chunk`) | present in every supported liblsl; pylsl degrades gracefully if absent |
| `StreamInlet.pull_chunk(min_samples=...)` | no extra liblsl requirement (implemented in Python on top of the regular chunk pull) |

Note that `transp_sync_blocking` is a flag value, not a symbol, so pylsl cannot
detect its absence: passing it to an older liblsl will simply be ignored or
misinterpreted by that library.

### Which liblsl do the PyPI wheels bundle?

The platform-specific wheels (`win32`, `win_amd64`, `macosx_11_0_universal2`,
`manylinux` x86_64) bundle the liblsl release named by the `LSL_RELEASE` /
`LSL_RELEASE_URL` variables at the top of `.github/workflows/publish-to-pypi.yml`
(currently `v1.18.0.b5`). The pure-Python `none-any` wheel bundles no library at all;
it relies on a liblsl you install yourself (see "liblsl loading" above).

### Checking at runtime

```python
import pylsl

pylsl.library_version()  # e.g. 118 -> liblsl 1.18.x
pylsl.library_info()  # build/branch details of the loaded library
pylsl.MIN_LIBLSL_VERSION  # 116 -> the oldest liblsl this pylsl supports
```

# For maintainers

## Continuous Integration

pylsl uses continuous integration and distribution. GitHub Actions will upload a new release to pypi whenever a Release is created in GitHub.

The version number is not stored in the source tree; it is derived from the git tag by
setuptools-scm (see `[tool.setuptools_scm]` in `pyproject.toml`). Creating a GitHub
Release with a tag like `v1.18.4` is what sets the published version. Before creating
the release, review the `LSL_RELEASE` / `LSL_RELEASE_URL` variables in **both**
`.github/workflows/publish-to-pypi.yml` (the liblsl bundled into the platform wheels)
and `.github/workflows/ci.yml` (the liblsl tested against), and update the "liblsl
compatibility" section above if the minimum supported liblsl changed.

### Linux Binaries Deprecated

We recently stopped building binary wheels for Linux. In practice, the `manylinux` dependencies were often incompatible with real systems.

## Manual Distribution

1. Manual way:
    1. `rm -Rf build dist *.egg-info`
    1. `uv build` (produces the sdist and the pure-Python wheel in `dist/`)
    1. `twine upload dist/*`
    * Note: the platform-specific wheels with a bundled liblsl are produced by the
      `publish-to-pypi` GitHub Actions workflow, not by this manual path.
1. For conda
    1. build liblsl: `conda build ../liblsl/`
    1. `conda build .`

# Known Issues with Multithreading on Linux

* At least for some versions of pylsl, it has been reported that running on Linux one cannot call ``pylsl`` functions from a thread that is not the main thread. This has been reported to cause access violations, and can occur during pulling from an inlet, and also from accessing an inlets info structure in a thread.
* Recent tests with multithreading (especially when safeguarding library calls with locks) using Python 3.7.6. with pylsl 1.14 on Linux Mint 20 suggest that this issue is solved, or at least depends on your machine. See https://github.com/labstreaminglayer/pylsl/issues/29

# Acknowledgments

Pylsl was primarily written by Christian Kothe while at Swartz Center for Computational Neuroscience, UCSD. The LSL project was funded by the Army Research Laboratory under Cooperative Agreement Number W911NF-10-2-0022 as well as through NINDS grant 3R01NS047293-06S1. pylsl is maintained primarily by Chadwick Boulay. Thanks for contributions, bug reports, and suggestions go to Bastian Venthur, David Medine, Clemens Brunner, and Matthew Grivich.
