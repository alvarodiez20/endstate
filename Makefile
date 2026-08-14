.PHONY: help install test lint typecheck check build clean docs docs-build gpu-up gpu-down bench determinism

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install dev dependencies
	uv sync --group dev

test:  ## Run the test suite
	uv run pytest

lint:  ## Lint
	uv run ruff check .
	uv run ruff format --check .

typecheck:  ## Type check
	uv run mypy

check: lint typecheck test  ## Everything CI runs

build:  ## Build sdist + wheel
	uv build

clean:  ## Remove build artefacts
	rm -rf dist build site .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

# --- Docs -----------------------------------------------------------------

docs:  ## Serve the docs locally with live reload
	uv run --group docs mkdocs serve

docs-build:  ## Build the docs the way CI does (warnings are errors)
	uv run --group docs mkdocs build --strict

# --- Infrastructure -------------------------------------------------------
# `gpu-down` exists before `gpu-up` on purpose. A forgotten node pool costs
# more than this entire project.

gpu-down:  ## Destroy the GPU node pool (run this every time)
	cd infra/terraform && terraform destroy -target=google_container_node_pool.gpu -auto-approve

gpu-up:  ## Create the GPU node pool
	cd infra/terraform && terraform apply -auto-approve

bench:  ## Run the eval suite against every configured provider
	uv run endstate eval --suite tasks/ --out benchmarks/

determinism:  ## Run the suite three times and report the flake rate
	uv run endstate eval --suite tasks/ --repeat 3 --out benchmarks/
