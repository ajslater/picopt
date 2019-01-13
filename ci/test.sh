#!/bin/sh
docker run -tiv /tmp/test-results:/tmp/test-results picopt-builder bin/tests.sh
