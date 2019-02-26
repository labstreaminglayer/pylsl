# pylsl

[![Build Status](https://travis-ci.com/labstreaminglayer/liblsl-Python.svg?branch=master)](https://travis-ci.com/labstreaminglayer/liblsl-Python)
[![Build status](https://ci.appveyor.com/api/projects/status/ggouc09585l2518i/branch/master?svg=true)](https://ci.appveyor.com/project/cboulay/liblsl-python/branch/master)

This is the Python interface to the [Lab Streaming Layer (LSL)](https://github.com/sccn/labstreaminglayer).
LSL is an overlay network for real-time exchange of time series between applications,
most often used in research environments. LSL has clients for many other languages
and platforms that are compatible with each other.

Let us know if you encounter any bugs (ideally using the issue tracker on
the GitHub project).

# Installation

## Prepared distributions

Note: The manylinux wheels are currently broken. We are awaiting manylinux2010 rollout. Follow [here](https://github.com/pypa/manylinux/issues/179).

The following platforms are supported with direct installation from [pypi](https://pypi.org/project/pylsl/)
using [pip](https://pip.pypa.io/en/stable/installing/): `pip install pylsl`

|   | macOS 10.6+ | manylinux i686 | manylinux x86_64 |  Windows 32bit | Windows 64bit |
|---|---|---|---|---|---|
| Python 2.7 | ✅ |  |  | ✅ | ✅ |
| Python 3.4 | ✅ |  |  | ✅ | ✅ |
| Python 3.5 | ✅ |  |  | ✅ | ✅ |
| Python 3.6 | ✅ |  |  | ✅ | ✅ |
| Python 3.7 | ✅ |  |  | ✅ | ✅ |

More or less experimental releases are in [tstenner's anaconda repo](https://anaconda.org/tstenner/pylsl), install with `conda install -c tstenner pylsl`.

## Self-built

If your platform is not supported by any of the prepared distributions then you will have to find or build a liblsl shared library for your platform.
You might be able to find the appropriate liblsl shared object (*.so on Linux, *.dylib on MacOS, or *.dll on Windows) from the [liblsl release page](https://github.com/sccn/liblsl/releases).
* Copy the shared object into `liblsl-Python/pylsl/lib` (use `cp -L` on platforms that use symlinks).
* From the `liblsl-Python` working directory, run `pip install .`.
    * Note: You can use `pip install -e .` to install while keeping the files in-place. This is convenient for developing pylsl.

# Usage

See the examples in pylsl/examples. Note that these can be run directly from the commandline with (e.g.) `python -m pylsl.examples.SendStringMarkers`.

# For maintainers

## Continuous Integration

pylsl uses continuous integration. It uses AppVeyor for Windows and Linux, and Travis-CI for MacOS.
Whenever a new commit is pushed, AppVeyor and Travis build liblsl, copy it into the correct directory, install pylsl, then test its basic functionality.
In addition, whenever a new `git tag` is used on a commit that is pushed to the master branch,
the CI systems will deploy new wheels to pypi.

## Manual Distrubtion

1. Manual way:
    1. `rm -Rf build dist *.egg-info`
    1. `python setup.py sdist bdist_wheel`
    1. `twine upload dist/*`
1. For conda
    1. build liblsl: `conda build ../liblsl/`
    1. `conda build .`

# Known Issues

* On Linux one currently cannot call ``pylsl`` functions from a thread that is not the main thread.

# Acknowledgments

Pylsl was primarily written by Christian Kothe while at Swartz Center for
Computational Neuroscience, UCSD. The LSL project was funded by the Army
Research Laboratory under Cooperative Agreement Number W911NF-10-2-0022 as
well as through NINDS grant 3R01NS047293-06S1. Thanks for contributions,
bug reports, and suggestions go to Bastian Venthur, Chadwick Boulay,
David Medine, Clemens Brunner, and Matthew Grivich.
