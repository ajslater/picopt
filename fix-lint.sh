#!/bin/bash
set -euxo pipefail
poetry run isort --color .
poetry run black .
npm run fix
npx prettier --write --parser ini setup.cfg
shellharden --replace ./*.sh ./**/*.sh
