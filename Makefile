.PHONY: help install dev lint format test data-manifest splits preprocess fixed-15m optimize optimize-smoke results report report-clean report-quarto reproduce reproduce-report final-portfolio docker-build docker-test docker-reproduce clean

PYTHON ?= python3
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
	$(PYTHON) -m preprocessing.materialize_processed_data

fixed-15m:  ## Run the fixed-parameter 15-minute cross-asset experiment runner
	$(PYTHON) -m strategy_development.local_implementation.run_fixed_15m_experiments

optimize:  ## Run the full Workstream C train/validation optimization suite
	$(PYTHON) -m strategy_development.local_implementation.optimization.run_all_optimizations

optimize-smoke:  ## Run the small smoke-mode Workstream C optimization suite
	$(PYTHON) -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke

results:  ## Generate cost-aware baseline and optimization result artifacts
	$(PYTHON) -m strategy_development.local_implementation.run_fixed_15m_experiments
	$(PYTHON) -m strategy_development.local_implementation.optimization.run_all_optimizations

report-quarto:  ## Render the optional Quarto Workstream C report if Quarto is installed
	quarto render reports/workstream_c_optimization_report.qmd

report:  ## Render the final Quarto report if Quarto is installed
	quarto render reports/final_report.qmd

report-clean:  ## Remove generated Quarto report artifacts only
	$(PYTHON) -c "from pathlib import Path; import shutil; root = Path('.'); \
[shutil.rmtree(path, ignore_errors=True) for path in [root / 'reports' / '_site', root / '.quarto']]; \
[path.unlink() for pattern in ['reports/*.html', 'reports/*.pdf', 'reports/*.docx'] for path in root.glob(pattern) if path.is_file()]; \
[shutil.rmtree(path, ignore_errors=True) for pattern in ['*_cache', '*_files'] for path in (root / 'reports').glob(pattern) if path.is_dir()]"

reproduce:  ## Run the deterministic research pipeline locally
	$(PYTHON) -m strategy_development.local_implementation.reproduce

reproduce-report:  ## Regenerate report inputs with practical deterministic commands, then render Quarto
	$(PYTHON) -m preprocessing.materialize_processed_data
	$(PYTHON) -m strategy_development.local_implementation.run_fixed_15m_experiments
	$(PYTHON) -m strategy_development.local_implementation.optimization.run_all_optimizations --smoke
	$(PYTHON) -m final_portfolio.run_report
	quarto render reports/final_report.qmd

final-portfolio:  ## Run final portfolio construction: grid search, figures, and report
	$(PYTHON) -m final_portfolio.run_report

docker-build:  ## Build the Docker image
	docker build -t intraday-momentum-repro .

docker-test:  ## Run tests inside Docker
	docker compose run --rm test

docker-reproduce:  ## Build the image and run the deterministic pipeline in Docker
	docker compose up --build reproduce

docker-report:  ## Build the image and render the full Quarto report in Docker
	docker compose up --build report

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
