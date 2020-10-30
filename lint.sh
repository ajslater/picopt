#!/bin/bash
# Lint checks
set -eux
poetry run isort --check-only --color .
poetry run black --check .
npx prettier --check .
# hadolint Dockerfile*
shellcheck -x ./*.sh
