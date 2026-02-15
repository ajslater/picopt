.PHONY: fix
## Fix django lint errors
## @category Fix
fix::
	 uv run --group lint djlint --reformat **/templates/**/*.html

.PHONY: lint
## Fix django lint errors
## @category Lint
lint::
	 uv run --group lint djlint --lint **/templates/**/*.html

.PHONY: dev-server
## Run the dev webserver
## @category Serve
dev-server:
	./bin/dev-server.sh

.PHONY: docs-server
## Run the docs server
## @category Docs
docs-server:
	uv run --only-group docs --no-dev mkdocs serve --open --dirty
