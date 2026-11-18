# AI setup verification map

This folder is the maintained source for verifying the AI setup of this checkout. Read this index first, then the feature file. `$H` is `$(git rev-parse --show-toplevel)/.agents/skills/verify-ai-setup/verify`.

## Baseline preconditions

- `$H launch --label <what> <kinds>`, then `$H doctor` (or `$H doctor --no-agents` when no session drive is planned). Require `doctor: PASS`.
- Never drive a fixture of a run that another checkout launched. The doctor `checkout` line shows the root.

## Driving conventions

- Start each recipe from a freshly launched fixture unless the recipe names an earlier step.
- Drives that share a `session_id` share router state. Give each recipe its own `session_id`.
- A session prompt that wants a gate to fire says that it is a throwaway test repo and names the exact command. Without that, the agent follows the global rules and never runs the command, and the gate is not driven.
- `$H cleanup` at the end. It keeps the evidence.

## Proof and skip reporting

- Hook proof: the `decision:` line and the rules fired. Session proof: the `[ai gate <id>]` line in the stream, the tool call, and `remote heads changed: no` for a deny.
- CLI proof: the transcript, the exit code and `git status --short` after. Installer proof: the planned lines and `real files changed: none`.
- Report an unreachable path with the command you ran and what blocks it.

## Feature entry contract

Each feature file has an H1, one paragraph, then `Sub-features`, `How to get to it (user POV)`, `Driving it with verify`, `Gotchas` and `Proof paths`.

## Features (full sweep order)

1. [Installer dry run](./installer.md): `install.sh --dry-run --yes` per profile.
2. [Playwright per profile](./playwright-per-profile.md): the plugin from the installer, the MCP from `ai-adopt --tools browser`.
3. [ai-adopt](./ai-adopt.md): the project layer on each fixture kind. Later features use the adopted fixtures.
4. [ai-check-detect](./ai-check-detect.md): the check commands per stack.
5. [ai-doctor project checks](./ai-doctor.md): `ai-doctor --project-only` on an adopted fixture.
6. [ai-precommit](./ai-precommit.md): the pre-commit lint on staged files.
7. [agent-audit](./agent-audit.md): the audit of a folder before use.
8. [Skill card](./skill-card.md): the session start text.
9. [Router gates](./router-gates.md): deny and pass, by payload and in a real session.
10. [Stop rules](./stop-rules.md): the turn end of a bug prompt.
11. [Verify hooks](./verify-hooks.md): planned, tickets 02 to 05.
12. [Dev worktree never syncs the live machine](./dev-worktree-no-sync.md): a git merge in a dotfiles dev worktree changes no live link.

Then the flows in [../multi-surface-journeys.md](../multi-surface-journeys.md).
