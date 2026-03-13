.PHONY: dev test test-cov lint format clean docker-build docker-up

# ─── Development ───────────────────────────────────────────────────────────────

dev:
	uvicorn sovereignguard.main:app --reload --port 8000

# ─── Testing ───────────────────────────────────────────────────────────────────

test:
	TARGET_API_KEY=test-key pytest tests/ -v --tb=short

test-cov:
	TARGET_API_KEY=test-key pytest tests/ -v --tb=short --cov=sovereignguard --cov-report=term-missing --cov-report=html

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint:
	ruff check sovereignguard/ tests/
	mypy sovereignguard/ --ignore-missing-imports --no-strict-optional

format:
	ruff format sovereignguard/ tests/

# ─── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker build -t sovereignguard:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ─── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage dist/ build/ *.egg-info/
