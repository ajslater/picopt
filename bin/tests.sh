#!/bin/bash
set -xeuo pipefail
mkdir -p /tmp/test-results/nose
nosetests-2.7 \
    --with-coverage \
    --cover-package=picopt \
    --with-xunit \
    --xunit-file=/tmp/test-results/nose/noseresults-2.7.xml
rm -f .coverage
nosetests-3.4 \
    --with-coverage \
    --cover-package=picopt \
    --with-xunit \
    --xunit-file=/tmp/test-results/nose/noseresults-3.4.xml
