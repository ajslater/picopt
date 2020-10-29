#!/bin/sh
mkdir -p dist
docker run -ti \
    -v dist:/project/dist \
    picopt-builder \
    ./build.sh
