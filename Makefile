.PHONY: setup setup-dev test test-unit test-integration run dev dev-rest dev-mcp inspect-mcp lint typecheck clean

setup:
	python -m pip install -e .

setup-dev:
	python -m pip install -e ".[dev]"
	pre-commit install || true

test:
	pytest tests/ -v --tb=short --cov=core --cov=api --cov=payments --cov=compliance --cov=mcp_server --cov=interfaces

test-unit:
	pytest tests/ -v --tb=short -m "not integration"

test-integration:
	pytest tests/ -v --tb=short -m integration

run:
	uvicorn api.main:app --host 0.0.0.0 --port 8402 --reload

dev:
	python scripts/dev_server.py

dev-rest:
	FAIRFETCH_TEST_MODE=true uvicorn api.main:app --host 0.0.0.0 --port 8402 --reload

dev-mcp:
	npx @modelcontextprotocol/inspector python -m mcp_server.server

inspect-mcp: dev-mcp

lint:
	ruff check . --fix
	ruff format .

typecheck:
	mypy core api payments compliance mcp_server interfaces --ignore-missing-imports

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache dist *.egg-info
