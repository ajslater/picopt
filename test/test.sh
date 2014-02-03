#!/bin/sh
PICOPT=../picopt.py

TEST_DIR=test_tmp

rm -rf $TEST_DIR
cp -a test_files $TEST_DIR

python $PICOPT $TEST_DIR/images/*
python $PICOPT -rcT $TEST_DIR
python $PICOPT -rcT $TEST_DIR
