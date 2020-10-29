#!/bin/sh
docker run -ti \
    -v /home/circleci/project/test-results:/project/picopt/test-results \
    picopt-builder \
    ./test.sh
