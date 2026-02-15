SHELL := /usr/bin/env bash

.PHONY: install-deps-npm
## Update pip and install node packages
## @category Install
install-deps-npm:
	npm install

.PHONY: update-npm
## Update npm dependencies
## @category Update
update-npm:
	./bin/update-deps-npm.sh

.PHONY: update
## Update dependencies
## @category Update
update:: update-npm

.PHONY: update-devenv
## Update development environment
## @category Update
update-devenv:
	bin/update-devenv.sh

.PHONY: kill-eslint_d
## Kill eslint daemon
## @category Lint
kill-eslint_d:
	bin/kill-eslint_d.sh

.PHONY: fix
## Fix lint errors
## @category Fix
fix::
	./bin/fix.sh

.PHONY: lint
## Lint
## @category Lint
lint::
	./bin/lint.sh

## Test
## @category Test
T :=
.PHONY: test
## Run Tests. Use T variable to run specific tests
## @category Test
test::
	./bin/test.sh $(T)

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md

.PHONY: clean
## Clean caches
## @category Build
clean::
	 rm -rf .*cache
