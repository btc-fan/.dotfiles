# verify-ai-setup: graphify works check (after review fixes)

Commit e4a1eb0. Doctor: PASS. Real files changed: none.

| Drive | Action | Result |
|---|---|---|
| 01-cli.txt | `ai-doctor --works graphify` (graphify with the mcp extra, no LLM backend) | `PASS graphify works`, rc 0 |
| 02-cli.txt | the same, with a fake graphify whose query fails like 0.9.118 without anyio | `FAIL graphify: graphify query: ModuleNotFoundError: No module named 'anyio'`, rc 1 |
| 03-install-dev-mac.txt | `install.sh --dry-run --profile dev-mac --user` | plans `uv tool install --force --no-build graphifyy\[mcp\]==0.9.119`; real files changed: none |
