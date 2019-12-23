#!/bin/sh
mkdir -p /tmp/test-results/nose
poetry run nosetests \
    --with-coverage \
    --cover-package=picopt \
    --with-xunit \
    --xunit-file=/tmp/test-results/nose/noseresults.xml
poetry run mypy picopt tests
