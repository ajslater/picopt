#!/bin/bash
set -euxo pipefail
mkdir -p test-results
poetry run coverage erase # coverage leaves junk around probbaly because my program exits uncleanly
poetry run pytest
poetry run coverage erase # coverage leaves junk around probbaly because my program exits uncleanly
poetry run mypy picopt tests

