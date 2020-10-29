#!/bin/sh
mkdir -p test-results
docker run -ti \
    -v test-results:/project/test-results \
    picopt-builder \
    ./test.sh
