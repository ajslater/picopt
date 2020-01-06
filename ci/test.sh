#!/bin/sh
docker run -ti \
    -v /home/circleci/project/test-results:/opt/picopt/test-results \
    picopt-builder \
    ./test.sh
