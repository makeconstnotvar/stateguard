PYTHON ?= python
REPO ?= .

.PHONY: install test lint validate-kit smoke clean build

install:
	$(PYTHON) -m pip install -e '.[dev,validation,smt]'

test:
	PYTHONPATH=src $(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m compileall -q src tests z3
	@if command -v ruff >/dev/null 2>&1; then ruff check src tests; fi

validate-kit:
	./scripts/validate-kit.sh

smoke:
	./scripts/smoke-test.sh

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

build: clean test validate-kit
	$(PYTHON) -m build
