.PHONY: help install dev lint format test data-manifest splits preprocess reproduce docker-build docker-test docker-reproduce clean

PYTHON ?= python
PIP ?= pip

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install project dependencies
	$(PIP) install -e .

dev:  ## Install project with dev dependencies and pre-commit hooks
	$(PIP) install -e ".[dev]"
	pre-commit install

lint:  ## Run ruff linter
	ruff check strategy_development/local_implementation/ preprocessing/ tests/

format:  ## Auto-format code with ruff
	ruff format strategy_development/local_implementation/ preprocessing/ tests/
	ruff check --fix strategy_development/local_implementation/ preprocessing/ tests/

test:  ## Run the offline pytest suite
	pytest

data-manifest:  ## Build a deterministic manifest for committed raw data
	$(PYTHON) -m preprocessing.build_data_manifest

splits:  ## Build deterministic global train/validation/test split boundaries
	$(PYTHON) -m preprocessing.make_global_splits

preprocess:  ## Run deterministic preprocessing foundation steps
	$(MAKE) data-manifest
	$(MAKE) splits

reproduce:  ## Run the deterministic research pipeline locally
	$(PYTHON) -m strategy_development.local_implementation.reproduce

docker-build:  ## Build the Docker image
	docker build -t intraday-momentum-repro .

docker-test:  ## Run tests inside Docker
	docker compose run --rm test

docker-reproduce:  ## Build the image and run the deterministic pipeline in Docker
	docker compose up --build reproduce

clean:  ## Remove caches, build products, and generated outputs
	$(PYTHON) -c "from pathlib import Path; import shutil; \
root = Path('.'); \
[shutil.rmtree(root / rel, ignore_errors=True) for rel in ['docs/_build', '.pytest_cache', '.ruff_cache', 'build', 'dist']]; \
[shutil.rmtree(path, ignore_errors=True) for path in root.glob('*.egg-info')]; \
[shutil.rmtree(path, ignore_errors=True) for path in root.rglob('__pycache__') if path.is_dir()]; \
[path.unlink() for path in root.rglob('*.pyc') if path.is_file()]; \
outputs = [root / 'outputs', root / 'outputs' / 'tables', root / 'outputs' / 'figures', root / 'outputs' / 'report', root / 'outputs' / 'manifests']; \
[path.mkdir(parents=True, exist_ok=True) for path in outputs]; \
[shutil.rmtree(path, ignore_errors=True) or path.mkdir(parents=True, exist_ok=True) for path in outputs[1:]]; \
[(path / '.gitkeep').touch() for path in outputs]"
