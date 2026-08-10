.PHONY: help install test lint typecheck check build clean gpu-up gpu-down bench

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
	rm -rf dist build .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage

# --- Infrastructure -------------------------------------------------------
# `gpu-down` exists before `gpu-up` on purpose. A forgotten node pool costs
# more than this entire project.

gpu-down:  ## Destroy the GPU node pool (run this every time)
	cd infra/terraform && terraform destroy -target=google_container_node_pool.gpu -auto-approve

gpu-up:  ## Create the GPU node pool
	cd infra/terraform && terraform apply -auto-approve

bench:  ## Run the eval suite against every configured provider
	uv run endstate eval --suite tasks/ --out benchmarks/
