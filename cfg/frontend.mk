.PHONY: fix-frontend
## Fix only frontend lint errors
## @category Lint
fix-frontend:
	bash -c "cd frontend && make fix"

.PHONY: fix
## Fix lint errors
## @category Lint
fix:: fix-frontend

.PHONY: lint-frontend
## Lint the frontend
## @category Lint
lint-frontend:
	bash -c "cd frontend && make lint"

.PHONY: lint-frontend
## Lint
## @category Lint
lint:: lint-frontend
	
.PHONY: dev-frontend-server
## Run the vite dev frontend
## @category Run
dev-frontend-server:
	bash -c "cd frontend && make dev-server"
