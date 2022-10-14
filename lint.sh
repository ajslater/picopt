#!/bin/bash
# Lint checks
set -euxo pipefail
poetry run pytest --ignore=tests .
poetry run pyright
poetry run bandit -r -c "pyproject.toml" --confidence-level=medium --severity-level=medium picopt
poetry run vulture .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
fi
npm run lint
npx prettier --check --parser ini setup.cfg
npm run check
if [ "$(uname)" = "Darwin" ]; then
    # shellcheck disable=2035
    hadolint *Dockerfile
    shellharden ./*.sh ./**/*.sh
    circleci config check .circleci/config.yml
fi
shellcheck --external-sources ./*.sh
poetry run codespell .
