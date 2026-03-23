PYTHON ?= python3

.PHONY: install format lint typecheck test api demo daily-run

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

format:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy .

test:
	$(PYTHON) -m pytest

api:
	$(PYTHON) -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload

demo:
	$(PYTHON) -m apps.cli demo run --frozen-time 2026-04-01T12:00:00Z --base-root artifacts/demo_runs/week3_demo

daily-run:
	$(PYTHON) -m apps.cli daily run --artifact-root artifacts/daily_runs/latest --requested-by make_daily_run
