PYTHON ?= python3.12

.PHONY: setup dev test check eval live
setup:
	$(PYTHON) scripts/configure.py
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r backend/requirements.lock
	cd frontend && npm ci

dev:
	.venv/bin/python scripts/dev.py

test:
	cd backend && ../.venv/bin/python -m pytest -q

check:
	.venv/bin/ruff check backend scripts
	cd frontend && npm run build

eval:
	PYTHONPATH=backend .venv/bin/python scripts/evaluate.py

live:
	.venv/bin/python scripts/live_smoke.py
