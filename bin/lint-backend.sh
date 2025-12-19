#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run --group lint ruff check .
uv run --group lint ruff format --check .
uv run --group lint basedpyright
uv run --group lint vulture .
if [ "$(uname)" = "Darwin" ]; then
  # Complexity is only of interest to development
  bin/lint-backend-complexity.sh
fi
# uv run djlint templates --profile=django --lint

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
  # Hadolint & shfmt are difficult to install on linux
  # shellcheck disable=2035
  # hadolint *Dockerfile
  shellharden --check ./**/*.sh
  # subdirs aren't copied into docker builder
  # .env files aren't copied into docker
  shellcheck --external-sources ./**/*.sh
  # circleci config validate .circleci/config.yml
fi
./bin/roman.sh -i .prettierignore .
uv run --group lint codespell .
