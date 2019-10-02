#!/bin/sh
VERSION=$1

# Build
flit build
python setup.py build bdist_wheel

# Upload
flit publish
twine upload dist/picopt-$1*
