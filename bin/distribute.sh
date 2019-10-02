#!/bin/sh
VERSION=$1
twine upload dist/picopt-$1*
