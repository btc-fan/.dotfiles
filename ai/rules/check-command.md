# check command (`ai-check-detect`, `check-fast` / `check` targets)

Our own tool (Tier 1 T1, owner plan 2026-11-12, built 2026-11-14). Detection ladder copied from nixpacks (MIT,
`src/providers/{python.rs,node/mod.rs,go.rs,rust.rs}`, read 2026-11-12); the test and lint part is ours.

## Vendor rules (verbatim)
NOT FOUND (our own tool; nixpacks has no rules text for agents).

## When / when not
- `check-fast`: lint + unit tests, no network, no services, target under 60 s. The Stop hook runs it.
- `check`: everything (full tests, type check where configured; long tier also `ai-ledger --check` and
  `ai-ratchet`). Run it before a PR; CI runs it.
- `ai-adopt` writes both as one marked block in the Makefile (or the justfile when only a justfile exists).
  A target that exists is never changed; a rerun replaces only the marked block. It runs `check-fast` once and
  writes the seconds into the Map line `- Check:`.
- Not for monorepos (workspaces, lerna, nx, turbo, rush, go.work, two or more package manifests below the root):
  refused with a message; write one target per package by hand and one root target that calls them.
- Not when the files tell nothing (no tests folder, no lint config): refused; write the targets by hand.

## Enforcement
- L4 (hooks): `stop-check` runs `check-fast` before the agent stops (see `stop-check.md`); the PR gate wants
  `Verify:` with the command and its output.
- L7: `ai-doctor --project` warns when an adopted repo has no `check-fast` or `check` target.
- Rules text: the Done block in the repo AGENTS.md (item 1: `make check` passes).

## Proof
- Should fire (EN): `ai-adopt --dry-run` in a uv + pytest repo prints "would write Makefile" and the block.
- Should fire (RO): "configureaza comanda de verificare pentru proiectul asta" (the agent proposes `ai-adopt`).
- Should fire (RU): "настрой команду проверки для этого репо" (the agent proposes `ai-adopt`).
- Should not fire: a pnpm workspace (refused, nothing written); a repo whose Makefile already has both targets.
- Signal: the Map line `- Check: ... measured N s`; `make -n check-fast` works. Tests: `ai/tests/test_tier1.py`
  (`t_detect_*`, `t_plan_keeps_targets`, `t_adopt_*`).

## Setup checklist
- Install: nothing extra (stdlib Python, part of `ai/bin`). Per OS: `make` (macOS command line tools; Ubuntu
  `make`) or `just`.
- Files touched per project: `Makefile` or `justfile` (marked block), `AGENTS.md` (Map line, Done item 1).
- Telemetry, auto-update, keys: none.
- Per project: `ai-adopt` (or `ai-adopt --no-measure`); tune the commands inside the block by hand if needed.
- Verify: `ai-check-detect --dir <repo>` prints the stack and both commands; `make check-fast` in the repo.
- Cleanup: delete the block between `# >>> ai checks` and `# <<< ai checks <<<`.
