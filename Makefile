PYTHON ?= python3

.PHONY: install format lint typecheck test api

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
