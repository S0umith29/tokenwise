# tokenwise

> **See exactly where your Claude tokens go — and stop wasting them.**

[![CI](https://github.com/sowmithkuppa/tokenwise/actions/workflows/ci.yml/badge.svg)](https://github.com/sowmithkuppa/tokenwise/actions/workflows/ci.yml)
[![CodeQL](https://github.com/sowmithkuppa/tokenwise/actions/workflows/codeql.yml/badge.svg)](https://github.com/sowmithkuppa/tokenwise/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/sowmithkuppa/tokenwise/badge)](https://securityscorecards.dev/viewer/?uri=github.com/sowmithkuppa/tokenwise)
[![PyPI](https://img.shields.io/pypi/v/tokenwise-cli)](https://pypi.org/project/tokenwise-cli/)
[![Python](https://img.shields.io/pypi/pyversions/tokenwise-cli)](https://pypi.org/project/tokenwise-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<!-- GIF placeholder -->
![tokenwise dashboard demo](https://via.placeholder.com/800x400.png?text=tokenwise+dashboard+demo+GIF+here)

---

## Security

> **tokenwise makes zero network calls. It only reads Claude Code's local logs. Audit it in 5 minutes.**

This tool reads sensitive data (your Claude session logs). Here is exactly what it does and does not do:

| Guarantee | How it's enforced |
|---|---|
| No network calls | Runtime assertion checks `sys.modules` at startup; grep CI check |
| Read-only on `~/.claude/` | Only `open(path, 'r')` touches that directory; unit tested |
| No `eval` / `exec` / `pickle` / `subprocess` | Grep CI check on every push |
| No telemetry or "phone home" | See above — no network stack imported |
| Cache stored with `0o700` / `0o600` perms | Enforced in `storage.py` |
| JSON-only serialization | No pickle, no exec of user-controlled data |

**Audit it yourself** — paste these into your terminal after cloning:

```bash
# Should return nothing (no network imports)
grep -rE "import (requests|urllib|httpx|socket|http\.client)" src/

# Should return nothing (no code execution)
grep -rE "\b(eval|exec|pickle|subprocess|os\.system)\b" src/

# Should return nothing (no writes to the Claude log directory)
grep -rE 'open\(.*["\'][wa+]' src/

# Confirm all file reads go through our safe_path() check
grep -rn "safe_path" src/tokenwise/
```

See [`THREAT_MODEL.md`](THREAT_MODEL.md) for the full analysis.

---

## What is tokenwise?

`tokenwise` reads your local Claude Code logs (`~/.claude/projects/`) and gives you a beautiful terminal breakdown of **exactly** how many tokens you've burned — by project, session, and day — with cost estimates and waste warnings.

Zero cloud sync. Zero telemetry. Pure read-only.

---

## Features

- **Live dashboard** — real-time token + cost view across all projects
- **Daily / weekly reports** — `tokenwise today`, `tokenwise week`
- **Per-project drill-down** — `tokenwise project <name>`
- **Waste detector** — `tokenwise waste` flags sessions with huge context for tiny output
- **CSV export** — `tokenwise export --csv`
- **Cache-aware cost** — distinguishes input, output, cache-write, and cache-read pricing
- Works **offline**, reads logs directly — no API key needed

---

## Install

```bash
pip install tokenwise-cli
```

Or with [pipx](https://pypa.github.io/pipx/) (recommended for CLI tools):

```bash
pipx install tokenwise-cli
```

### Requirements

Python **3.10 or later** is required. Check your version:

```bash
python3 --version
```

**Development setup** (for contributors):

```bash
git clone https://github.com/sowmithkuppa/tokenwise.git
cd tokenwise
python3.13 -m venv .venv          # or python3.10 / 3.11 / 3.12
source .venv/bin/activate
pip install -e ".[dev]"
make verify                        # runs tests + all security checks
```

---

## Quickstart

```bash
# Live dashboard (updates every 5 seconds)
tokenwise

# Today's usage
tokenwise today

# Last 7 days
tokenwise week

# Drill into a project
tokenwise project myapp

# Find wasteful sessions
tokenwise waste

# Export raw data
tokenwise export --csv > usage.csv
```

---

## How it works

Claude Code writes JSONL logs to `~/.claude/projects/<project-slug>/<session-id>.jsonl`. Each assistant message includes a `usage` object with `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens`. `tokenwise` parses these, applies current Anthropic pricing, and aggregates the results.

Parsed data is cached in `~/.tokenwise/cache.json` (permissions `0o600`) so repeated runs are instant.

---

## Comparison to `ccusage`

| Feature | tokenwise | ccusage |
|---|---|---|
| Live dashboard | ✅ | ❌ |
| Waste detection | ✅ | ❌ |
| Cache-aware cost | ✅ | partial |
| Per-session drill-down | ✅ | ✅ |
| CSV export | ✅ | ✅ |
| No API key required | ✅ | ✅ |
| Formal threat model | ✅ | ❌ |
| Runtime no-network assertion | ✅ | ❌ |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Pricing data lives in `src/tokenwise/pricing.py`. If Anthropic updates their prices, PRs to update that file are very welcome.

---

## License

MIT © Sowmith Kuppa
