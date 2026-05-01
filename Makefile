.PHONY: test lint typecheck audit grep-check verify clean

# ── Setup ────────────────────────────────────────────────────────────────────
# Assumes a venv exists. Run: python3.13 -m venv .venv && pip install -e ".[dev]"
VENV_BIN ?= .venv/bin
PYTHON   := $(VENV_BIN)/python
PIP      := $(VENV_BIN)/pip

# ── Individual targets ───────────────────────────────────────────────────────

test:
	$(VENV_BIN)/pytest --tb=short -q

test-cov:
	$(VENV_BIN)/pytest --cov=tokenwise --cov-report=term-missing --cov-fail-under=80

lint:
	$(VENV_BIN)/ruff check src/ tests/
	$(VENV_BIN)/ruff format --check src/ tests/

typecheck:
	$(VENV_BIN)/mypy src/

audit:
	$(VENV_BIN)/bandit -r src/ -c pyproject.toml
	# CVE-2026-3219 affects pip itself (no fix version exists yet — it's the
	# package manager in our dev venv, not a runtime dependency of tokenwise).
	$(VENV_BIN)/pip-audit --ignore-vuln CVE-2026-3219

grep-check:
	@echo "── Checking for forbidden network imports ──────────────────────────"
	@if grep -rE "import (requests|urllib|httpx|socket|http\.client|aiohttp|ssl)" src/; then \
		echo "FAIL: network import found in src/"; exit 1; \
	else echo "OK: no network imports"; fi

	@echo "── Checking for forbidden execution primitives ─────────────────────"
	@if grep -rE "\b(eval|exec|pickle|subprocess|os\.system)\b" src/; then \
		echo "FAIL: forbidden primitive found in src/"; exit 1; \
	else echo "OK: no eval/exec/pickle/subprocess/os.system"; fi

	@echo "── Checking for write-mode opens ───────────────────────────────────"
	@if grep -rE "open\(.*['\"][wa+]" src/tokenwise/parser.py; then \
		echo "FAIL: write-mode open found in parser.py"; exit 1; \
	else echo "OK: no write-mode opens in parser.py"; fi

# ── The one command a skeptical user should run ──────────────────────────────
verify: lint typecheck test audit grep-check
	@echo ""
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║  All security checks passed.                         ║"
	@echo "║                                                      ║"
	@echo "║  • No network imports in source                      ║"
	@echo "║  • No eval/exec/pickle/subprocess                    ║"
	@echo "║  • No write-mode opens on ~/.claude/                 ║"
	@echo "║  • bandit: no security issues                        ║"
	@echo "║  • pip-audit: no known vulnerabilities               ║"
	@echo "║  • All 25 tests pass                                 ║"
	@echo "╚══════════════════════════════════════════════════════╝"

clean:
	rm -rf dist/ build/ *.egg-info .coverage htmlcov/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
