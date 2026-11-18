# Playwright per profile

The installer installs the `ai-playwright@ai` Claude plugin turned off on every profile. A project turns the browser tool on with `ai-adopt --tools browser`, which installs the pinned `@playwright/mcp` after an audit.

## Sub-features

- `pw-plugin`: install.sh installs `ai-playwright@ai` and sets `enabledPlugins/ai-playwright@ai = false`.
- `pw-mcp`: `ai-adopt --tools browser` installs `@playwright/mcp@<pin>` into `~/.local/share/ai/npm/playwright-mcp-<version>`.
- `pw-audit`: the MCP install needs an audit result; dev-mac skips the npm audit (owner decision 2026-11-14, ticket 16).

## How to get to it (user POV)

- Install or update the setup (the plugin part).
- In a web project: `ai-adopt --tools browser` (the MCP part).

## Driving it with verify

Preconditions: a run with `web-app`, `doctor: PASS`.

- **Plugin per profile.** Run `$H drive install dev-mac` and `$H drive install server`. Both print `claude plugin install ai-playwright@ai --scope user` and `enabledPlugins/ai-playwright@ai = false` under `playwright lines`.
- **MCP plan per profile.** Run `$H drive cli --fixture web-app AI_PROFILE=dev-mac ai-adopt --tools browser --yes --no-onboard --dry-run` and the same with `AI_PROFILE=server`. Both print `would install @playwright/mcp@0.0.85 into <tmp>/home/.local/share/ai/npm/playwright-mcp-0.0.85 (integrity + agent-audit checked first)`.

## Gotchas

- The pin moves: read the version from `playwright-mcp` in the installer's step 2 table, not from this file.
- A dry run stops before the audit. The dev-mac audit skip ("audit skipped: profile dev-mac") shows only in a real `--tools browser` run, which downloads the package. Ticket 16 owns that fix.

## Proof paths

- success: both profiles plan the plugin (off) and the MCP install.
- cancel: `--dry-run` is the back-out: `git status --short after` stays empty.
- error: n/a in a dry run. A failed audit on server needs a real run (see Unreachable).
- empty: a fixture without `--tools browser`: `ai-adopt` prints no Playwright line.
- persistence: n/a for a dry run.
- Unreachable: the real MCP install and its audit result per profile. Blocked by: it downloads from npm and needs skill-scanner, osv-scanner and guarddog in the temp HOME (see agent-audit.md). Route tried: the dry run above.
