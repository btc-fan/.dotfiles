# stop-check (Stop hook: `check-fast` before "done")

Our own hook (Tier 1 T2), `ai/marketplace/plugins/ai-core/hooks/stop-check.py`. Patterns read 2026-11-12:
anthropics `ralph-loop` stop-hook.sh (Apache-2.0: session isolation, counter) and the pydevtools pre-commit
Stop hook (git change detection; rewritten, no license stated).

## Vendor rules (verbatim)
NOT FOUND (our own hook). Platform rules it follows: Claude Stop accepts `{"decision": "block", "reason"}` and sets
`stop_hook_active` on the continuation; Codex Stop "expects JSON on stdout when it exits 0. Plain text output is
invalid" (https://developers.openai.com/codex/hooks.md, read 2026-11-12).

## When / when not
- Runs at every Stop of Claude and Codex in an adopted repo (`.ai/enabled`), tier `mvp` or `long`.
- Off: tier `try`, a `no-stop-check` line in `.ai/enabled`, a repo without `.ai/enabled`, a repo without a
  `check-fast` target.
- Silent when nothing changed since the session start (baseline fingerprint at SessionStart, so a tree that was
  dirty before the session is not blamed), when the tree is already green, and on success.
- Coexists with oh-my-claudecode: while an OMC persistent mode (ralph, autopilot, ultragoal, team ...) of this
  session is active, OMC owns the stop and this hook is silent; it runs at the first stop after the mode ends.
  Both hooks are silent when `stop_hook_active` is true. So one stop never gets two blocks and the chain ends.

## Enforcement
- L4 hook: JSON `decision: block` with the command, the exit code and the last 40 lines; at most 2 blocks per
  tree (then one note to the owner); 55 s timeout counts as a pass with a note; exit 0 with 0 tests seen fails
  (minimum-input floor); long tier: `ai-ratchet --only tests,skips --no-write` after a green check.
- Long tier: a note (Claude `systemMessage`) when files in a regression-ledger area changed by Bash (`sed -i`).
- What it cannot see: a check that passes but proves little beyond the floor; CI stays the real wall.

## Proof
- Should fire (EN): "change the price rounding in src/app.py" in an adopted mvp repo with a failing test: the
  stop is blocked with "make check-fast failed".
- Should fire (RO): "schimba rotunjirea pretului si termina" (same repo): blocked once, twice, then a note.
- Should fire (RU): "поменяй округление цены и закончи" (same repo): blocked with the last 40 lines.
- Should not fire: a question with no file change ("what does this function do?"); the same edit in a repo with
  tier `try`.
- Signal: the block reason starts `[ai stop-check]`; state in `~/.local/state/ai/stop/`. Tests:
  `ai/tests/test_tier1.py` (`t_stop_*`, real OMC run noted in ai/SPEC-LOG.md).

## Setup checklist
- Install: part of the ai-core plugin (`hooks.json` and `codex-hooks.json`: SessionStart and Stop entries,
  `/usr/bin/python3`). Linux admin installs copy the Codex entry into `/etc/codex/hooks.json`.
- Codex trusts hooks per script hash: after an update run `ai-sync` (or trust once in `/hooks`).
- Telemetry, keys: none. State: `~/.local/state/ai/stop/<session>-<repo>.json` (mode 600, pruned after 7 days).
- Per project: a `check-fast` target (ai-adopt), tier in `.ai/enabled`, opt out with `no-stop-check`.
- Verify: `ai-doctor` (hook files valid, Codex hooks trusted); `python3 ai/tests/test_tier1.py`.
- Cleanup: remove the two stop-check entries from both hooks files; delete `~/.local/state/ai/stop/`.
