# agent-audit

`agent-audit` checks a package, folder, skill or plugin before use and appends one line to `~/.local/state/ai/audit.log`. The audit-before-install gate reads that log.

## Sub-features

- `audit-dir`: `agent-audit dir <path>` scans a folder.
- `audit-skill-required`: a folder with skills needs skill-scanner; without a result it is exit 5.
- `audit-usage`: a wrong form prints the usage, exit 2.

## How to get to it (user POV)

- Agents run it before an install (the gate asks for it). The owner runs it on a downloaded folder.

## Driving it with verify

Preconditions: a `docs-only` fixture, `doctor: PASS`.

- **Folder without skills.** Before ai-adopt: `$H drive cli --fixture docs-only --timeout 600 agent-audit dir <fixture path>`. Expect `-- skill-scanner: not applicable (no SKILL.md, ...)`, `agent-audit: nothing found`, `rc: 0`.
- **Usage.** `$H drive cli --fixture docs-only agent-audit <fixture path>`: the usage text, `rc: 2`.
- **Folder with skills.** After ai-adopt on the same fixture: `$H drive cli --fixture docs-only --timeout 600 agent-audit dir <fixture path>`. Seen on 2026-11-18: `ERROR: skill-scanner not installed`, then `agent-audit: ERROR: skill-scanner was required (a skill or plugin) but gave no result`, `rc: 5`. The adopted fixture has `.claude/` skill links, so it counts as a skill folder.

## Gotchas

- The scanners live under the real HOME. The temp HOME of the driver has none, so a folder with skills ends in ERROR (exit 5) here, never in PASS.
- The audit line goes to the temp HOME's `audit.log`, not the owner's.

## Proof paths

- success: the folder without skills, `nothing found`, `rc: 0`.
- cancel: n/a.
- error: the exit 5 drive above.
- empty: the same folder without skills (skill-scanner not applicable).
- persistence: the line in `<tmp>/home/.local/state/ai/audit.log` (read it before cleanup).
- Unreachable: a PASS for a folder with skills. Blocked by: the scanners are not in the temp HOME, and the real HOME is off limits. Route tried: `agent-audit dir`.
