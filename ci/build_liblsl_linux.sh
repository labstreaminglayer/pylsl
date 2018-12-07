#!/bin/sh
set -e -x

pwd
ls -all

# Install system packages required to build liblsl
apk update && apk add cmake linux-headers patchelf git ninja g++

# Get and build liblsl
git clone https://github.com/sccn/liblsl.git
cd liblsl
mkdir build && cd build
cmake -DCMAKE_INSTALL_PREFIX=../../pylsl/ -DLSL_UNIXFOLDERS=ON -DLSL_SO_LINKS_STDCPP_STATIC=ON -G Ninja ..
ninja install -v
cd ../..
patchelf --set-rpath '$ORIGIN' pylsl/lib/liblsl64.so.*
cp -L /lib/libc.musl-x86_64.so.1 pylsl/lib/
