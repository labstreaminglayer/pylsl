#!/bin/bash
set -e -x

# Install a system package required by our library
# yum install -y atlas-devel

# Get and build liblsl
git clone https://github.com/sccn/liblsl.git
cd liblsl
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../../pylsl/ -DLSL_UNIXFOLDERS=ON
cmake --build . --target install
cd ../..

# Compile wheels
for PYBIN in /opt/python/*/bin; do
#    "${PYBIN}/pip" install -r /host/dev-requirements.txt
    "${PYBIN}/pip" wheel /host/ -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/*.whl; do
    auditwheel repair "$whl" --plat linux_x86_64 -w /host/wheelhouse/
done

# Install packages and test
for PYBIN in /opt/python/*/bin/; do
    "${PYBIN}/pip" install pylsl --no-index -f /host/wheelhouse
    (cd "$HOME"; "${PYBIN}/python" -c "import pylsl; print(pylsl.library_version()); print(pylsl.local_clock())")
done
