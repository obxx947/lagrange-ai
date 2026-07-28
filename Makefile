# ============================================================
# Lagrange Tactical AI — Makefile
# Multi-target build automation for the fleet combat platform
# Usage: make [target]
#   make help       - Show all available commands
#   make start      - Start the server
#   make dev        - Start in development mode with hot reload
#   make test       - Run test suite
#   make lint       - Run all linters
#   make build      - Build frontend and backend
#   make docker     - Build Docker image
#   make deploy     - Deploy to Kubernetes
#   make clean      - Clean all artifacts
# ============================================================

# ---- Configuration ----
PYTHON := python
PIP := pip
NODE := node
NPM := npm
DOCKER := docker
KUBECTL := kubectl
PORT := 3000
HOST := 127.0.0.1
LAGRANGE_HOME := $(shell pwd)

.PHONY: help start stop restart status install test lint build dev \
        docker docker-build docker-up docker-down \
        k8s-deploy k8s-status k8s-logs \
        backup clean rebuild rebuild-index export ships \
        format check audit all

# ---- Help ----
help: ## Show all available commands
	@echo "Lagrange Tactical AI — Build Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---- Service management ----
start: ## Start the Lagrange server
	@echo "[Lagrange] Starting server on $(HOST):$(PORT)..."
	@$(PYTHON) main.py

dev: ## Start in development mode with hot reload
	@echo "[Lagrange] Development mode with hot reload..."
	@uvicorn main:app --host $(HOST) --port $(PORT) --reload --reload-dir . --log-level debug

stop: ## Stop the Lagrange server
	@echo "[Lagrange] Stopping server..."
	@taskkill /F /IM python.exe 2>nul || pkill -f "main.py" || true

restart: stop start ## Restart the server

status: ## Check server health
	@curl -s http://$(HOST):$(PORT)/health 2>/dev/null | $(PYTHON) -m json.tool || echo "[Lagrange] Server is not running"

# ---- Installation ----
install: ## Install all dependencies
	@echo "[Lagrange] Installing Python dependencies..."
	@$(PIP) install -r requirements.txt --no-cache-dir
	@echo "[Lagrange] Installing frontend dependencies..."
	@$(NPM) install --no-audit --no-fund
	@echo "[Lagrange] Parsing ship database..."
	@$(NODE) parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json
	@echo "[Lagrange] Building vector index..."
	@$(PYTHON) -c "from rag_service import build_vector_index; build_vector_index()"
	@echo "[Lagrange] Installation complete"

install-dev: ## Install with dev dependencies
	@$(PIP) install -e ".[dev]" --no-cache-dir
	@$(PIP) install -r requirements-dev.txt --no-cache-dir
	@pre-commit install
	@echo "[Lagrange] Dev installation complete"

# ---- Testing ----
test: ## Run the test suite
	@echo "[Lagrange] Running tests..."
	@$(PYTHON) -m pytest tests/ -v --tb=short --cov=lagrange --cov-report=term-missing

test-unit: ## Run unit tests only
	@$(PYTHON) -m pytest tests/ -v -m "unit" --tb=short

test-integration: ## Run integration tests
	@$(PYTHON) -m pytest tests/ -v -m "integration" --tb=short

test-coverage: ## Run tests with HTML coverage report
	@$(PYTHON) -m pytest tests/ -v --cov=lagrange --cov-report=html --cov-report=term
	@echo "[Lagrange] Coverage report: htmlcov/index.html"

# ---- Linting and formatting ----
lint: ## Run all linters
	@echo "[Lagrange] Python linting..."
	@$(PYTHON) -m ruff check .
	@echo "[Lagrange] Type checking..."
	@$(PYTHON) -m mypy src/ || true
	@echo "[Lagrange] JavaScript linting..."
	@$(NPM) run lint 2>/dev/null || true
	@echo "[Lagrange] Security audit..."
	@$(PYTHON) -m bandit -r . -ll 2>/dev/null || true

format: ## Auto-format all code
	@echo "[Lagrange] Formatting Python..."
	@$(PYTHON) -m black .
	@$(PYTHON) -m isort .
	@$(PYTHON) -m ruff check --fix .
	@echo "[Lagrange] Formatting JavaScript/TypeScript..."
	@$(NPM) run format 2>/dev/null || true

check: lint test ## Run full quality check (lint + test)

audit: ## Run security audit
	@echo "[Lagrange] Security audit..."
	@$(PYTHON) -m bandit -r . -ll -f json -o security-audit.json
	@$(NPM) audit 2>/dev/null || true

# ---- Build ----
build: ## Build frontend and backend packages
	@echo "[Lagrange] Building frontend..."
	@$(NPM) run build 2>/dev/null || true
	@echo "[Lagrange] Building Python package..."
	@$(PYTHON) -m build --wheel --no-isolation
	@echo "[Lagrange] Build complete: dist/"

# ---- Docker ----
docker-build: ## Build Docker image
	@echo "[Lagrange] Building Docker image..."
	@$(DOCKER) build -t lagrange-tactical-ai:latest -f Dockerfile .

docker-build-dev: ## Build development Docker image
	@echo "[Lagrange] Building dev Docker image..."
	@$(DOCKER) build -t lagrange-tactical-ai:dev -f Dockerfile.dev --target dev .

docker-up: ## Start Docker Compose stack
	@echo "[Lagrange] Starting Docker Compose..."
	@$(DOCKER) compose -f docker-compose.override.yml up -d

docker-down: ## Stop Docker Compose stack
	@echo "[Lagrange] Stopping Docker Compose..."
	@$(DOCKER) compose -f docker-compose.override.yml down

# ---- Kubernetes ----
k8s-deploy: ## Deploy to Kubernetes
	@echo "[Lagrange] Deploying to Kubernetes..."
	@$(KUBECTL) apply -f k8s/configmap.yaml
	@$(KUBECTL) apply -f k8s/secret.yaml
	@$(KUBECTL) apply -f k8s/deployment.yaml
	@$(KUBECTL) apply -f k8s/service.yaml
	@$(KUBECTL) apply -f k8s/ingress.yaml
	@echo "[Lagrange] K8s deployment applied"

k8s-status: ## Check Kubernetes deployment status
	@$(KUBECTL) get all -n lagrange

k8s-logs: ## Tail Kubernetes logs
	@$(KUBECTL) logs -f -n lagrange deployment/lagrange-agent

# ---- Data management ----
backup: ## Backup database
	@echo "[Lagrange] Creating database backup..."
	@$(PYTHON) -c "from database import backup_database; print(backup_database())"

rebuild-index: ## Rebuild vector index
	@echo "[Lagrange] Rebuilding vector index..."
	@$(PYTHON) -c "from rag_service import build_vector_index; build_vector_index()"

rebuild: rebuild-index ## Alias for rebuild-index

ships: ## Parse ship database
	@echo "[Lagrange] Parsing ship database..."
	@$(NODE) parse_ships.js lagrange_docs/lglrmax.html lagrange_docs/ship_database.json

export: ## Export ship data to CSV
	@echo "[Lagrange] Exporting ship data..."
	@$(PYTHON) export_ships.py all

# ---- Utility ----
clean: ## Clean all generated artifacts
	@echo "[Lagrange] Cleaning build artifacts..."
	@rm -rf __pycache__ *.pyc *.pyo .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
	@rm -rf dist/ build/ *.egg-info/ htmlcov/ coverage.xml 2>/dev/null || true
	@rm -rf node_modules/ .npm-cache/ .webpack-cache/ 2>/dev/null || true
	@rm -rf logs/*.log 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "[Lagrange] Clean complete"

clean-all: clean ## Deep clean including databases
	@echo "[Lagrange] Deep cleaning..."
	@rm -rf chroma_db/ db_backup/ data/ 2>/dev/null || true
	@rm -f *.db *.db-journal 2>/dev/null || true

# ---- All-in-one ----
all: install build start ## Full install, build, and start
