#!/bin/bash
set -euxo pipefail
export PYTHONPATH=.
mkdir -p test-results
PYTHONDONTWRITEBYTECODE=1 poetry run pytest "$@"
