export MERGE_PYTHON=1

.PHONY: install-deps-pip
## Update pip and install node packages
## @category Install
install-deps-pip: install-deps-npm
	pip install --upgrade pip

.PHONY: install
## Install for production
## @category Install
install-prod: install-deps-pip
	uv sync --no-install-project --no-dev

.PHONY: install-dev
## Install dev requirements
## @category Install
install-dev: install-deps-pip
	uv sync --no-install-project

.PHONY: install-all
## Install with all extras
## @category Install
install-all: install-deps-pip
	uv sync --no-install-project --all-extras

.PHONY: clean
## Clean caches
## @category Build
clean::
	find . -name "__pycache__" -print0 | xargs -0 rm -rf
	rm -rf .coverage

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

.PHONY: update-python
## Update python dependencies
## @category Update
update-python:
	./bin/update-deps-python.sh

.PHONY: update
## Update dependencies
## @category Update
update:: update-python update-npm

.PHONY: fix
## Fix python lint errors
## @category Fix
fix::
	./bin/fix-python.sh

.PHONY: typecheck
## Static typecheck
## @category Lint
typecheck:
	uv run --group lint basedpyright .

.PHONY: ty
## Static typecheck with ty
## @category Lint
ty:
	uv run --group lint ty check .

.PHONY: complexity
## Lint backend complexity
## @category Lint
complexity:
	./bin/lint-complexity.sh

.PHONY: lint
## Lint python 
## @category Lint
lint::
	./bin/lint-python.sh

.PHONY: uml
## Create a UML class diagram
## @category Lint
uml:
	bin/uml.sh

.PHONY: cycle
## Detect Circular imports
## @category Lint
cycle:
	uvx pycycle --ignore node_modules,.venv --verbose --here

## Test Python
## @category Test
T :=
.PHONY: test
## Run Python Tests. Use T variable to run specific tests
## @category Test
test::
	./bin/test-python.sh $(T)

## Show version. Use V variable to set version
## @category Update
V :=
.PHONY: version
## Show or set project version
## @category Update
version:
	bin/version.sh $(V)
