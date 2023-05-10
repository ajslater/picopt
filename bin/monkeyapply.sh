#!/bin/bash
# apply monkeytype to all python files
set -euo pipefail
poetry run monkeytype list-modules | xargs -L 1 poetry run monkeytype apply
