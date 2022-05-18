#!/bin/bash
rm -rf /tmp/test
cp -a /tmp/walk /tmp/test
./run.sh -rtx ZIP /tmp/test
