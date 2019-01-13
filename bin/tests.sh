#!/bin/bash
set -xeuo pipefail
nosetests-2.7 --with-coverage --cover-package=picopt
nosetests-3.4 --with-coverage --cover-package=picopt
