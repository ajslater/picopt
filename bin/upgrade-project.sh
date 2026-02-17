#!/bin/bash
# Upgrade an old project to devenv managed
set -euo pipefail
DEVENV=../devenv
mv Makefile Makefile.orig.mk
mv eslint.config.js eslint.config.orig.js
OLD_SCRIPTS=(clean.sh create-output-dirs.sh docker-build.sh fix-lint-backend.sh lint-backend-complexity.sh lint-backend.sh makefile-help.mk monkeyapply.sh monkeyrun.sh sortignore.sh update-deps.sh venv-upgrade.sh)
for f in "${OLD_SCRIPTS[@]}"; do
  rm -f bin/"$f"
done
cp -a "$DEVENV"/bin "$DEVENV"/init/Makefile "$DEVENV"/init/eslint.config.js .
uv pip install semver tomlkit
