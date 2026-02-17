#!/bin/sh
# create output directories with correct perms for ci builder docker mounts
mkdir -p -m 777 test-results dist
chown -R circleci:circleci test-results dist
