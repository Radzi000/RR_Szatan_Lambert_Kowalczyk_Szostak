.PHONY: install dev lint format test docs docker-build docker-test backtest clean help

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
	ruff check intraday_momentum/ tests/

format:  ## Auto-format code with ruff
	ruff format intraday_momentum/ tests/
	ruff check --fix intraday_momentum/ tests/

test:  ## Run tests with coverage
	pytest --tb=short

docs:  ## Build Sphinx HTML documentation
	sphinx-build -b html docs docs/_build/html
	@echo "Documentation built in docs/_build/html/"

docker-build:  ## Build Docker image
	docker build -t intraday-momentum .

docker-test:  ## Run tests inside Docker container
	docker compose run --rm app

backtest:  ## Run backtesting (requires data)
	$(PYTHON) -m intraday_momentum.backtest

clean:  ## Remove build artifacts and caches
	rm -rf __pycache__ .pytest_cache .ruff_cache
	rm -rf docs/_build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

download-data:  ## Download fresh SPY data from Yahoo Finance
	$(PYTHON) -c "\
	import yfinance as yf; import pandas as pd; \
	d=yf.download('SPY',start='2017-01-01',interval='1d',progress=False); \
	d.columns=d.columns.get_level_values(0) if isinstance(d.columns,pd.MultiIndex) else d.columns; \
	d.to_csv('data/spy_daily.csv'); print(f'Daily: {len(d)} rows'); \
	m=yf.download('SPY',period='60d',interval='5m',progress=False); \
	m.columns=m.columns.get_level_values(0) if isinstance(m.columns,pd.MultiIndex) else m.columns; \
	m.to_csv('data/spy_5m.csv'); print(f'5min: {len(m)} rows')"
