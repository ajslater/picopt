#!/bin/bash
set -euxo pipefail
mkdir -p test-results
poetry run pytest
# poetry run coverage combine
#poetry run coverage report
#poetry run coverage html
poetry run mypy picopt tests
