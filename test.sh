#!/bin/sh

TEST_DIR=test_tmp

rm -rf $TEST_DIR
cp -a test_files $TEST_DIR

./picopt.py -rcT $TEST_DIR
./picopt.py -rcT $TEST_DIR
