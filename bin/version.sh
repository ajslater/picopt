#!/bin/bash
# Get or set version.
set -euo pipefail
VERSION="${1:-}"
if [ "$VERSION" = "" ]; then
  poetry version | awk '{print $2};'
else
  poetry version "$VERSION"
fi
