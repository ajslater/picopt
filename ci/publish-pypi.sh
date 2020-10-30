#!/bin/bash
# publish to pypi with poetry using environment variable credentials
set -euo pipefail
poetry publish -u "$PYPI_USER" -p "$PYPI_PASS"
