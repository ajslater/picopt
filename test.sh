#!/bin/bash
set -euxo pipefail
mkdir -p test-results
poetry run pytest
poetry run coverage erase # py-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
