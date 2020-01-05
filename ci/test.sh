#!/bin/sh
docker run -tiv /home/circleci/project/test-results:/opt/picopt/test-results picopt-builder bin/tests.sh
