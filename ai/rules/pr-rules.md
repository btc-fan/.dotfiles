# pr-rules gate (PR body parts and tier fields)

Our own gate in `hooklib.py` (`gate_pr`). Tier fields added 2026-11-14 (Tier 1 T4). Rules copied as ideas from
tests-checker-action (MIT), the SwiftLint Dangerfile (MIT) and the Zed dangerfile (GPL, idea only: reject
placeholder text), read 2026-11-12.

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
- Every `gh pr create` and `gh pr edit` with a body (also behind `rtk` and `rtk proxy`).
- Always: a ```mermaid block and the `<!-- author-sessions` block.
- Tier `mvp` (default, also outside adopted repos): `Verify:` (check command and the tail of its output),
  `Risk:` (one line). Tier `long`: also `Docs:` (files, or "none, because ..."), `Changed guards:` (each edited or
  removed test and why, or "none"), and on a fix PR `Ledger: R-NNN`. Tier `try`: the two blocks only.
- Placeholder text (`TODO`, `TBD`, `<...>`, `...`, `n/a`) counts as missing.
- A `fix:` PR (title `fix`, `bugfix`, `hotfix`) needs a test file in its diff against the base (mvp, long).
- Over 400 changed lines (lockfiles and generated files left out): a warning, never a block.
- `--fill`, `--fill-first`, `--fill-verbose`, `--web`: refused (the gate cannot see the body).

## Enforcement
- L4 gate, deny (Codex: deny with `decision: block`). Owner skip: `sudo ai-gate-skip pr-rules <min> <why>`.
- L0: `ai/agents-md/50-pull-requests.md` lists the parts.
- No diff (no base branch found): the test-file and size checks are skipped with a note in the context.

## Proof
- Should fire (EN): `gh pr create --title x --body "fix"` (BLOCK).
- Should fire (RO): "deschide un PR cu titlul fix: rotunjire" with no test in the diff (BLOCK).
- Should fire (RU): "создай PR" with `Verify: TODO` in the body (BLOCK).
- Should not fire: a body with mermaid, Verify, Risk and the author-sessions block (mvp); `gh pr edit 12
  --add-label bug`.
- Signal: `DENY pr-rules` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/pr-rules.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Per project: the tier line in `.ai/enabled` (ai-adopt).
- Verify: `bash ai/tests/run.sh -k pr-rules`; `ai-doctor --live` canary (a PR without the blocks is denied).
- Cleanup: none (the rule is part of the router); a project lowers its tier to need fewer fields.
