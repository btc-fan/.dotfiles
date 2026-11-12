# GitHub MCP (github/github-mcp-server)

Pin: github-mcp-server v2.1.0 (Go release binary). Audit at install (SPEC section 21). Source: https://github.com/github/github-mcp-server

## Vendor rules
No recommended rule text found. Features: toolsets, `--read-only` / `GITHUB_READ_ONLY`, lockdown mode (docs/server-configuration.md).

## When / when not
- GitHub work: issues, pull requests, review comments. Use this MCP or `gh`.
- owner/repo comes from the origin remote (`git remote get-url origin`). The `github` row shows it. Never ask the owner for it.
- Access is FULL (owner decision, SPEC section 4). Pushes, merges and issue edits are outward actions: confirm with the owner first, as the root rules say.
- Not for local git. Use git.

## Knowledge home, freshness, maintenance
- Home: none on purpose. Issues and PRs change all the time, so a cache would go stale. Read them live each time.
- The repo slug is derived live from the origin remote. Nothing to maintain.

## Enforcement
- L3: routing row `github` (adds "Repo: owner/repo"). L4: `pr-rules` gate on `gh pr create|edit`. `secret-scan` gate on git commit and push.
- The token comes from `~/.config/ai/secrets.env` as `GITHUB_PERSONAL_ACCESS_TOKEN`, loaded by `mcp/github.sh`.

## Proof
- Should fire (EN): "list open pull requests and read the review comments on #12".
- Should fire (RO): "arata-mi issue-urile deschise din repo".
- Should fire (RU): "покажи открытые pull request в этом репо".
- Should not fire: "git log last 5 commits".
- Signal: tool_use `mcp__plugin_ai-core_github__*` or a `gh` Bash call, with the owner and repo of the origin remote and no question to the owner about it.

## Setup checklist
1. Create a fine-grained token (owner). Put it in `~/.config/ai/secrets.env` (mode 600).
2. Install pinned per `ai/pins.env`. Entry in the ai-core `.mcp.json`.
3. At install: download the release binary, check the release checksum, run `agent-audit dir` on the tag source. Telemetry: UNVERIFIED, check in that audit. Use `GITHUB_READ_ONLY` only if the owner asks (access is FULL by decision).
4. Verify: `claude mcp list` shows it connected. Ask for the owner login with the user tool.
5. Cleanup: remove the entry. Revoke the token.
Audit at install, not yet done (SPEC section 21).
