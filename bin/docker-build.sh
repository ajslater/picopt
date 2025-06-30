#!/bin/bash
# run all phases of build with docker
set -euo pipefail
docker compose build picopt-build-builder
docker compose up --exit-code-from picopt-lint picopt-lint
docker compose up --exit-code-from picopt-test picopt-test
docker compose up --exit-code-from picopt-build picopt-build
