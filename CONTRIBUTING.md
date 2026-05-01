# Contributing to tokenwise

Thank you for helping improve tokenwise.

## Setup

```bash
git clone https://github.com/sowmithkuppa/tokenwise.git
cd tokenwise
python3.13 -m venv .venv          # Python 3.10+ required
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest                        # run all tests
pytest tests/test_security.py # run security tests only
pytest --cov=tokenwise        # with coverage
```

## Lint and type-check

```bash
ruff check src/ tests/        # linter
ruff format src/ tests/       # formatter
mypy src/                     # type checker
```

## Security checks (run before every PR)

```bash
make verify                   # runs all of the above + bandit + pip-audit + grep checks
```

Or individually:

```bash
bandit -r src/ -c pyproject.toml

pip-audit

# No network imports
grep -rE "import (requests|urllib|httpx|socket|http)" src/

# No forbidden execution primitives
grep -rE "\b(eval|exec|pickle|subprocess)\b" src/
```

## Security review expectations for PRs

Every PR that touches `src/` must pass `make verify` locally before requesting review.

PRs that modify any of the following require an explicit explanation in the PR description:
- `src/tokenwise/security.py`
- `src/tokenwise/parser.py` (the module with read access to `~/.claude/`)
- `src/tokenwise/storage.py` (the module with write access to `~/.tokenwise/`)
- `.github/workflows/` (any CI change)
- `pyproject.toml` (dependency changes)

New runtime dependencies require justification: what does it do, why is it needed, and why can't we use stdlib?

## Pricing updates

To update model pricing, edit `src/tokenwise/pricing.py`. Update the date comment at the top and verify the numbers match https://www.anthropic.com/pricing. Include the source URL in your PR description.

## Commit style

Use imperative mood: `Add X`, `Fix Y`, `Update Z`. Keep the subject line under 72 characters.

## Code style

This project uses `ruff` for formatting and linting. Run `ruff format src/ tests/` before committing. Comments in source code should explain *why*, not *what*. No block comments for obvious code.
