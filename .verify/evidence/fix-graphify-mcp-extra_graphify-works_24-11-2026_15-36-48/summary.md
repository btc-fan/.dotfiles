# verify-ai-setup: graphify works check

Commit a327666. Doctor: PASS. Real files changed: none.

| Drive | Action | Result |
|---|---|---|
| 01-cli.txt | `ai-doctor --works graphify` (graphify 0.9.118 with the mcp extra) | `PASS graphify works`, rc 0 |
| 02-cli.txt | the same, with `~/.local/bin` first on PATH | `PASS graphify works`, rc 0 |
| 03-cli.txt | the same, with a fake graphify whose query fails like 0.9.118 without anyio | `FAIL graphify: graphify query: ModuleNotFoundError: No module named 'anyio'`, rc 1 |
| 04-install-dev-mac.txt | `install.sh --dry-run --profile dev-mac --user` | plans `uv tool install --force --no-build graphifyy\[mcp\]==0.9.119`; real files changed: none |
