# pylsl

This is the Python interface to the [Lab Streaming Layer (LSL)](https://github.com/labstreaminglayer/labstreaminglayer).
LSL is an overlay network for real-time exchange of time series between applications,
most often used in research environments. LSL has clients for many other languages
and platforms that are compatible with each other.

Pylsl should work with any recent version of the ``liblsl`` library (which
is also included with this package), on any operating system and with any recent
Python version, including 2.7+ and 3.x.

Let us know if you encounter any bugs (ideally using the issue tracker on
the GitHub project).

# Installation

The preferred method of installation is to use [pip](https://pip.pypa.io/en/stable/installing/): `pip install pylsl`

# Usage

See the examples in pylsl/examples. Note that these can be run directly from the commandline with (e.g.) `python -m pylsl.examples.SendStringMarkers`.

# Development

If you are a developer or if you are a user that would like to submit a pull request,
then the easiest way to modify pylsl is to install it to your python environment in development mode:

1. Clone this repository.
1. Download the correct liblsl shared object (*.so on Linux, *.dylib on MacOS, or *.dll on Windows) from the [liblsl release page](https://github.com/labstreaminglayer/liblsl/releases) and copy it into this directory's pylsl folder.
    * On platforms with symlinks, be sure to use `cp -L` to copy the links correctly.
1. In a conda terminal / command prompt / terminal, make sure your preferred python environment is active.
1. `cd` to the root directory for this repository, then do `pip install -e .`

## For pypi maintainers

1. Manual way:
    1. `rm -Rf build dist *.egg-info`
    1. `python setup.py sdist bdist_wheel`
    1. `twine upload dist/*`
2. TODO: AppVeyor/Travis

# Known Issues

* On Linux one currently cannot call ``pylsl`` functions from a thread that is not the main thread.
* Though 

# Acknowledgments

Pylsl was primarily written by Christian Kothe while at Swartz Center for
Computational Neuroscience, UCSD. The LSL project was funded by the Army
Research Laboratory under Cooperative Agreement Number W911NF-10-2-0022 as
well as through NINDS grant 3R01NS047293-06S1. Thanks for contributions,
bug reports, and suggestions go to Bastian Venthur, Chadwick Boulay,
David Medine, Clemens Brunner, and Matthew Grivich.
