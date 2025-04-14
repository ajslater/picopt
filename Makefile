SHELL := /usr/bin/env bash

## Show version. Use V variable to set version
## @category Update
V :=
.PHONY: version
## Show or set project version
## @category Update
version:
	bin/version.sh $(V)

.PHONY: install-deps
## Update pip and install node packages
## @category Install
install-deps:
	pip install --upgrade pip
	npm install

.PHONY: install
## Install for production
## @category Install
install-prod: install-deps
	uv sync --no-install-project --no-dev

.PHONY: install-dev
## Install dev requirements
## @category Install
install-dev: install-deps
	uv sync --no-install-project

.PHONY: install-all
## Install with all extras
## @category Install
install-all: install-deps
	uv sync --no-install-project --all-extras

.PHONY: clean
## Clean pycaches
## @category Build
clean:
	 ./bin/clean-pycache.sh

.PHONY: build
## Build package
## @category Build
build:
	uv build

.PHONY: publish
## Publish package to pypi
## @category Deploy
publish:
	uv publish

.PHONY: update
## Update dependencies
## @category Update
update:
	./bin/update-deps.sh

.PHONY: kill-eslint_d
## Kill eslint daemon
## @category Lint
kill-eslint_d:
	bin/kill-eslint_d.sh

.PHONY: fix-backend
## Fix only backend lint errors
## @category Fix
fix-backend:
	./bin/fix-lint-backend.sh

.PHONY: fix
## Fix front and back end lint errors
## @category Fix
fix: fix-backend

.PHONY: typecheck
## Static typecheck
## @category Lint
typecheck:
	uv run pyright .

.PHONY: lint
## Lint front and back end
## @category Lint
lint: lint-backend

.PHONY: lint-backend
## Lint the backend
## @category Lint
lint-backend:
	./bin/lint-backend.sh

## Test
## @category Test
T :=
.PHONY: test
## Run Tests. Use T variable to run specific tests
## @category Test
test:
	./bin/test.sh $(T)

.PHONY: dev-server
## Run the dev webserver
## @category Run
dev-server:
	./bin/dev-server.sh

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md

.PHONY: all

include bin/makefile-help.mk
