#!/bin/bash
set -e -x

# Compile wheels.
for PYBIN in /opt/python/*/bin; do
    "${PYBIN}/pip" wheel . -w dist/
done

# Bundle external shared libraries into the wheels
for whl in dist/*.whl; do
    auditwheel repair "$whl" -w ./dist/
done
# Cleanup unneeded wheels
rm dist/*-linux_x86_64.whl

# Install packages and test. Only 3.7, 3.6, and 3.5 work.
#for PYBIN in /opt/python/*/bin; do
#    "${PYBIN}/pip" install pylsl --no-index -f ./dist
#    (cd "$HOME"; "${PYBIN}/python" -c "import pylsl; print(pylsl.library_version()); #print(pylsl.local_clock())")
#done
/opt/python/cp37-cp37m/bin/pip install pylsl --no-index -f ./dist
(cd "$HOME"; "/opt/python/cp37-cp37m/bin/python" -c "import pylsl; print(pylsl.library_version()); print(pylsl.local_clock())")
/opt/python/cp36-cp36m/bin/pip install pylsl --no-index -f ./dist
(cd "$HOME"; "/opt/python/cp36-cp36m/bin/python" -c "import pylsl; print(pylsl.library_version()); print(pylsl.local_clock())")
/opt/python/cp35-cp35m/bin/pip install pylsl --no-index -f ./dist
(cd "$HOME"; "/opt/python/cp35-cp35m/bin/python" -c "import pylsl; print(pylsl.library_version()); print(pylsl.local_clock())")

# Delete the unwanted wheels that we know will not work.
rm -f dist/*-cp27-cp27m-manylinux1_x86_64.whl
rm -f dist/*-cp27-cp27mu-manylinux1_x86_64.whl
rm -f dist/*-cp34-cp34m-manylinux1_x86_64.whl
