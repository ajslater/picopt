#!/bin/bash
# Update python and npm dependencies
set -euo pipefail
uv sync --no-install-project --all-extras --upgrade
uv lock --upgrade --dry-run
npm update
npm outdated
if [ -d frontend ]; then
  cd frontend
  npm update
  npm outdated
fi
