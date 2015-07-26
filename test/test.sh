#!/bin/sh
PICOPT='../picopt/picopt.py'
TEST_DIR='test_tmp'

rm -rf $TEST_DIR
cp -a test_files $TEST_DIR

python $PICOPT $* $TEST_DIR/images/*
python $PICOPT -rct $* $TEST_DIR
python $PICOPT -rct $* $TEST_DIR
