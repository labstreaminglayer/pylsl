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

See the examples in pylsl/examples. Note that these can be run directly from the commandline with (e.g.) `python -m pylsl.examples.{name-of-example}`.

You can get a list of the examples with `python -c "import pylsl.examples; help(pylsl.examples)"`

## liblsl loading

`pylsl` will search for `liblsl` first at the filepath specified by an environment variable named `PYLSL_LIB`, then in the package directory (default location for Windows), then finally in normal system library folders.

If the shared object is not installed onto a standard search path (or it is but can't be found for some [other bug](https://github.com/labstreaminglayer/pylsl/issues/48)), then we recommend that you copy it to the pylsl installed module path's `lib` subfolder. i.e. `{path/to/env/}site-packages/pylsl/lib`.

* The `site-packages/pylsl` path will only exist _after_ you install `pylsl` in your Pyton environment.
* You may have to create the `lib` subfolder.
* Use `python -m site` to find the "site-packages" path.
* Use `cp -L` on platforms that use symlinks.

Alternatively, you can use an the environment variable. Set the `PYLSL_LIB` environment variable to the location of the library or set `LD_LIBRARY_PATH` to the folder containing the library. For example,

1. `PYLSL_LIB=/usr/local/lib/liblsl.so python -m pylsl.examples.{name-of-example}`, or
2. `LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib python -m pylsl.examples.{name-of-example}`

# For maintainers

## Continuous Integration

pylsl uses continuous integration and distribution. GitHub Actions will upload a new release to pypi whenever a Release is created in GitHub.

### Linux Binaries Deprecated

We recently stopped building binary wheels for Linux. In practice, the `manylinux` dependencies were often incompatible with real systems.

## Manual Distribution

1. Manual way:
    1. `rm -Rf build dist *.egg-info`
    1. `python setup.py sdist bdist_wheel`
    1. Additional steps on Linux:
        * `auditwheel repair dist/*.whl -w dist`
        * `rm dist/*-linux_x86_64.whl`
    1. `twine upload dist/*`
1. For conda
    1. build liblsl: `conda build ../liblsl/`
    1. `conda build .`

# Known Issues with Multithreading on Linux

* At least for some versions of pylsl, is has been reported that running on Linux one cannot call ``pylsl`` functions from a thread that is not the main thread. This has been reported to cause access violations, and can occur during pulling from an inlet, and also from accessing an inlets info structure in a thread.
* Recent tests with mulithreading (especially when safeguarding library calls with locks) using Python 3.7.6. with pylsl 1.14 on Linux Mint 20 suggest that this issue is solved, or at least depends on your machine. See https://github.com/labstreaminglayer/pylsl/issues/29

# Acknowledgments

Pylsl was primarily written by Christian Kothe while at Swartz Center for Computational Neuroscience, UCSD. The LSL project was funded by the Army Research Laboratory under Cooperative Agreement Number W911NF-10-2-0022 as well as through NINDS grant 3R01NS047293-06S1. pylsl is maintained primarily by Chadwick Boulay. Thanks for contributions, bug reports, and suggestions go to Bastian Venthur, David Medine, Clemens Brunner, and Matthew Grivich.
