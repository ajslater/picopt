#!/bin/bash
set -euo pipefail
poetry run monkeytype list-modules | xargs -L 1 poetry run monkeytype apply
