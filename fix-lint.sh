#!/bin/bash
set -euxo pipefail
poetry run ruff --fix .
poetry run black .
npm run fix
shellharden --replace ./*.sh ./**/*.sh
