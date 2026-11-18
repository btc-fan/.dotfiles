# 16: three setup bugs: Playwright on dev-mac, the ai-adopt branch, Python tests

**What to build:** three refusals that block work and match no owner decision are fixed.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Playwright: on profile dev-mac, `ai-adopt --tools browser` installs the pinned `@playwright/mcp` with "audit skipped: profile dev-mac" (owner decision 2026-11-14). Profile server still needs a PASS.
- [x] ai-adopt branch: when a remote `ai-adopt` branch exists and its PR is merged, ai-adopt deletes it (remote and local) and starts fresh. An open PR on it: ai-adopt adds its commit to that branch. Seen in ScripTube: remote head `31a87c00` of merged PR #22.
- [x] Python tests: `ai-check-detect` finds a `tests/` folder with unittest or pytest files in a repo with no pyproject.toml, and adds the test command to check-fast (milu had 110 unittest tests left out).
