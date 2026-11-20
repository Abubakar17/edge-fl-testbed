.DEFAULT_GOAL := help
.PHONY: help setup lint format test protos sim sim-down clean

COMPOSE := docker compose -f deploy/docker/docker-compose.yml
PROTOS := $(wildcard src/edge_fl/comms/protos/*.proto)

help: ## List available targets
	@uv run --frozen python -c "import re; [print(f'  {m[0]:<10} {m[1]}') for m in re.findall(r'^([a-z-]+):.*?## (.*)$$', open('Makefile').read(), re.M)]"

setup: ## Create the local .venv (Python 3.11 + locked deps) and install git hooks
	uv sync --frozen
	uv run --frozen pre-commit install

lint: ## Ruff lint + format check, then mypy
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen mypy

format: ## Auto-fix lint issues and format code
	uv run --frozen ruff check --fix .
	uv run --frozen ruff format .

test: ## Run the test suite
	uv run --frozen pytest

protos: ## Regenerate Python code from the .proto files (commit the result)
	uv run --frozen python -m grpc_tools.protoc -I src --python_out=src --pyi_out=src --grpc_python_out=src $(PROTOS)

sim: ## Run the local docker-compose simulation (1 server + 3 clients)
	$(COMPOSE) up --build --abort-on-container-exit

sim-down: ## Stop and remove the simulation containers
	$(COMPOSE) down --remove-orphans

clean: ## Remove caches and build artifacts (keeps .venv, data/ and results/)
	uv run --frozen python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for pat in ('**/__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'build', 'dist', '**/*.egg-info') for p in pathlib.Path('.').glob(pat) if '.venv' not in p.parts]"
