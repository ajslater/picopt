#!/bin/bash
# apply monkeytype to all python files
set -euo pipefail
uv run monkeytype list-modules | xargs -L 1 uv run monkeytype apply
