# scripts/

Project-local helper scripts. Follow [`_ai/conventions.md`](../_ai/conventions.md) for style; when it does
not cover a case, mirror the scripts around it.

- Bash: shebang, `set -euo pipefail`, executable (`chmod +x`).
- Keep a header comment with a one-line `Description:` — tooling reads it.
- Invoke as `./scripts/<name>`.
