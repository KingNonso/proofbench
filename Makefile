# ProofBench Migration Court
#
# The five judge commands below must all work with provider variables unset.
#
# A target that cannot yet produce real evidence fails with an EVIDENCE_NOT_BUILT
# message naming what is missing. It never passes as a no-op. Note that make
# reports its own exit code 2 for any failed recipe; the underlying script exits
# 3, which is what a caller invoking it directly will see.

PYTHON_VERSION := 3.12
POSTGRES_IMAGE := postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94

.DEFAULT_GOAL := help
.PHONY: help bootstrap test baseline evaluate replay lint typecheck check clean

## ---------------------------------------------------------------------------
## The five judge commands
## ---------------------------------------------------------------------------

bootstrap: ## Install the pinned toolchain and pre-pull the database image
	uv python install $(PYTHON_VERSION)
	uv sync
	docker pull $(POSTGRES_IMAGE)
	echo "bootstrap complete"

test: ## Run unit, schema, security, and selected integration tests
	uv run pytest

baseline: ## Validate committed baseline trajectories and decisions
	@scripts/not-built.sh baseline "results/raw-runs.jsonl and committed baseline trajectories"

evaluate: ## Recompute metrics and verify committed run manifests
	@scripts/not-built.sh evaluate "results/summary.json and committed run manifests"

replay: ## Re-run deterministic checks for committed golden certificates
	@scripts/not-built.sh replay "tests/golden/*/certificate.json"

## ---------------------------------------------------------------------------
## Developer targets
## ---------------------------------------------------------------------------

lint: ## Ruff format check and lint
	uv run ruff format --check src tests scripts
	uv run ruff check src tests scripts

typecheck: ## mypy strict
	uv run mypy src

check: lint typecheck test ## Everything CI runs

clean: ## Remove caches and generated run artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

help: ## List targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## /{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
