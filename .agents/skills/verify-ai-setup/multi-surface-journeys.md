# Multi-surface journeys

Flows that cross surfaces. Each one starts from a fresh `$H launch` with the named kinds and `$H doctor`.

## Adopt, then a gate in a real session

CLI, then a headless agent session, then git state.

- **Adopt.** `$H drive cli --fixture docs-only ai-adopt --yes --no-onboard`. Expect `rc: 0` and the branch `ai-adopt` on the remote.
- **Session.** `$H drive session claude --fixture docs-only "<the router-gates.md deny prompt>"`. Expect `ai-core loaded from: <checkout>/ai/marketplace/plugins/ai-core`, `gates in output: merge-approval`, `remote heads changed: no`.
- **Codex.** The same prompt with `$H drive session codex`. Same end state.
- End state: the remote has `main` (launch) and `ai-adopt` (the adopt) and nothing else.

## Install plan, then the browser tool in a project

Installer, then CLI.

- **Install plan.** `$H drive install dev-mac`: the Playwright plugin is planned and off.
- **Browser tool.** `$H drive cli --fixture web-app AI_PROFILE=dev-mac ai-adopt --tools browser --yes --no-onboard --dry-run`: the MCP install is planned.
- End state: `real files changed: none`, `git status --short after` empty.

## Subagent in a worktree, then the turn end, then a commit

Session, then git state, then the pre-commit hook. The recipes are in [features/verify-hooks.md](features/verify-hooks.md).

- **Red.** A subagent with `isolation: "worktree"` writes a test by shell and makes no run: `verify-tool-used` blocks its stop twice.
- **Green.** The same subagent runs the skill's launch, doctor, drive and cleanup: its turn ends.
- **Commit.** A new test with no run newer than HEAD: the commit is refused; after the run named in the refusal it passes.
- End state: one `verify-tool-used` wall per red stop, a valid `run.log` in the worktree, the second commit in `git log`.

## Bug prompt, then the turn end

Hook payloads in one session: see stop-rules.md. A real session version is planned with ticket 14 (hint instead of stop).
