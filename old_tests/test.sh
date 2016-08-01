#!/bin/sh
PICOPT='../run.py'
TEST_DIR='test_tmp'

rm -rf $TEST_DIR
cp -a test_files $TEST_DIR

$PICOPT $* $TEST_DIR/images/*
$PICOPT -rct $* $TEST_DIR
$PICOPT -rct $* $TEST_DIR
