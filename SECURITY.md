# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | ✅ |

## Reporting a Vulnerability

If you discover a security issue in tokenwise, please **do not open a public GitHub issue**.

**Contact:** soumith.odu@gmail.com  
**Subject line:** `[tokenwise] Security vulnerability`

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional but appreciated)

**Response time commitment:**
- Acknowledgement within **48 hours**
- Status update within **7 days**
- Fix or mitigation plan within **30 days** for confirmed vulnerabilities

We will coordinate disclosure with you before publishing a fix or CVE.

## Scope

In scope:
- Path traversal or arbitrary file read/write via tokenwise
- Privilege escalation via the CLI
- Dependency vulnerabilities with user-exploitable impact
- Cache file permission issues (data exposure)

Out of scope:
- Vulnerabilities requiring physical access to the machine
- Social engineering
- Vulnerabilities in Claude Code itself (report to Anthropic)

## Security Design

tokenwise is designed with a minimal attack surface:

- **Read-only on `~/.claude/`**: tokenwise never writes to Claude Code's log directory. All file handles opened against that path are opened in `'r'` mode only, enforced in `src/tokenwise/security.py` and tested in `tests/test_security.py`.
- **No network calls**: tokenwise imports no network-capable modules. A runtime assertion at CLI startup (`assert_no_network_imports()`) verifies this. CI grep checks enforce it on every push.
- **No `eval`/`exec`/`pickle`/`subprocess`**: tokenwise only deserializes JSON. CI checks enforce this on every push.
- **Cache stored securely**: `~/.tokenwise/` is created with `0o700` permissions; `cache.json` is written with `0o600`.
- **Path safety**: all file reads go through `safe_read_path()`, which resolves symlinks and validates the path is within `~/.claude/projects/`. Writes go through `safe_write_path()` which enforces `~/.tokenwise/`.

See [`THREAT_MODEL.md`](THREAT_MODEL.md) for the full analysis.
