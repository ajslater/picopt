#!/bin/bash
set -euxo pipefail
export PYTHONPATH=.
mkdir -p test-results
PYTHONDONTWRITEBYTECODE=1 poetry run pytest "$@"
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
poetry run coverage erase
