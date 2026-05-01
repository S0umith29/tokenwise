# Threat Model — tokenwise

> **Summary**: tokenwise reads local JSONL files, computes cost aggregates, and displays them in the terminal. It touches no network, executes no user-controlled code, and writes only to its own cache directory.

---

## What data does tokenwise touch?

| Location | Access | Contents |
|---|---|---|
| `~/.claude/projects/` | **Read-only** | Claude Code session logs (JSONL). Contains your conversation text and token usage metadata. |
| `~/.tokenwise/cache.json` | Read + Write | Aggregated token/cost statistics. No conversation text. Mode `0o600`. |

tokenwise does **not** access:
- API keys or credentials
- `~/.claude/settings.json` or any Claude config
- Files outside the two directories above
- Any network resource

---

## Trust boundaries

```
┌────────────────────────────────────────────────┐
│  Your machine                                  │
│                                                │
│  ~/.claude/projects/   ─read──▶  tokenwise     │
│                                     │          │
│  ~/.tokenwise/cache   ◀──write──────┘          │
│                                     │          │
│  Terminal output       ◀────────────┘          │
│                                                │
│  [NO network boundary crossed]                 │
└────────────────────────────────────────────────┘
```

All processing is local. There is no server, no API call, no telemetry endpoint.

---

## Explicit guarantees and how they're enforced

### 1. No network calls
- tokenwise source imports no network-capable module (`socket`, `urllib`, `requests`, `httpx`, `http.client`, etc.)
- Enforced by: `assert_no_network_imports()` at CLI startup; CI grep check on every push; ruff `S` rules; `bandit` scan
- **Verify yourself**: `grep -rE "import (requests|urllib|httpx|socket|http)" src/` — must return nothing

### 2. Read-only access to `~/.claude/`
- All reads go through `open_readonly()` in `security.py`, which opens files in `'r'` mode only
- The path is validated by `safe_read_path()` before opening — resolves symlinks, checks `is_relative_to(~/.claude/projects)`
- Enforced by: unit tests in `tests/test_security.py::test_no_write_mode_opens_on_claude_dir`
- **Verify yourself**: `grep -rE "open\(.*['\"][wa+]" src/` — must return nothing for paths near `~/.claude`

### 3. No code execution of user data
- tokenwise deserializes JSONL using `json.loads()` only — no `eval`, `exec`, `pickle`, `yaml.load()`, or `subprocess`
- User-controlled strings from logs are never executed or passed to a shell
- Enforced by: CI grep check; `bandit` scan; `tests/test_security.py::test_no_eval_in_source` etc.
- **Verify yourself**: `grep -rE "\b(eval|exec|pickle|subprocess)\b" src/` — must return nothing

### 4. Secure cache permissions
- `~/.tokenwise/` is created with `os.chmod(dir, 0o700)` — user-only access
- `cache.json` is set to `os.chmod(file, 0o600)` after every write — user-read/write only
- Enforced by: `tests/test_security.py::test_ensure_cache_dir_creates_with_700` and `test_set_cache_file_permissions_600`

### 5. Path traversal prevention
- `safe_read_path()` calls `Path.resolve()` before checking `is_relative_to()` — symlinks are followed and checked
- A path like `~/.claude/projects/../../../etc/passwd` resolves to `/etc/passwd` and is rejected
- Enforced by: `tests/test_security.py::test_safe_read_path_rejects_traversal`

---

## Known limitations / out of scope

1. **The logs themselves may contain sensitive information** — conversation text, file paths, code snippets. tokenwise does not read or display conversation text, only token counts from the `usage` field. However, the files exist on your local disk with whatever permissions Claude Code set.

2. **Cache is unencrypted** — `~/.tokenwise/cache.json` stores aggregated token/cost data in plaintext JSON with `0o600` permissions. It contains no conversation text. If your threat model requires encryption at rest, this tool is not the right fit.

3. **Pricing data is hardcoded** — tokenwise uses hardcoded pricing constants. It does not call the Anthropic API. If Anthropic changes pricing, cost estimates will be incorrect until a new version is released.

4. **Dependency supply chain** — tokenwise depends on `click`, `rich`, and `pydantic`. Their security posture is not under our control. We run `pip-audit` and `dependency-review` on every PR to catch known CVEs.

5. **No integrity check on JSONL files** — tokenwise trusts the contents of `~/.claude/projects/` as-is. If another process has tampered with those files, tokenwise will parse tampered data. The JSONL files are on your local machine under your user's control — this is considered acceptable.

---

## What tokenwise will NEVER do

- Make network calls
- Write to `~/.claude/` in any mode
- Execute code from user-controlled log data
- Store conversation text in cache
- Collect or transmit usage analytics
