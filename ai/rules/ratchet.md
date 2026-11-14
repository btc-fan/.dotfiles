# ai-ratchet (counts that may only improve)

Our own counter script (Tier 1 T7). Ideas: basedpyright baseline, mypy-baseline, eslint-seatbelt (MIT, read
2026-11-12); none is used as a dependency.

## Vendor rules (verbatim)
NOT FOUND (our own tool).

## When / when not
- Long tier. Baseline `.ai/ratchet.json` (committed; `ai-adopt --tier long` runs `ai-ratchet --init`).
- Counters: `tests` (test definitions in test files: Python, JS/TS, Go, Rust), `skips` (skip and xfail marks,
  `it.skip`, `xit`, `t.Skip`, `#[ignore]`), `lint` (ruff where configured, or the project's own eslint).
- tests may only go up; skips and lint may only go down. A better count tightens the baseline (commit it).
- The reference is `.ai/ratchet.json` as committed at the base (merge base with origin/main or main; the session
  start commit in stop-check), not the working-tree file: lowering the file in the same change does not pass.
- Skips also count `pytestmark = pytest.mark.skip`, `collect_ignore` in conftest.py, and `--deselect` /
  `--ignore` in pytest config files and the Makefile/justfile.
- A test deleted or skipped on purpose: only with the owner's OK; then `ai-ratchet --reset`, and the PR lists it
  under `Changed guards:`.
- Not a coverage tool, and not a type-check baseline (use basedpyright's baseline when a repo adds a type
  checker).

## Enforcement
- `make check` runs `ai-ratchet` (long tier).
- `stop-check` runs `ai-ratchet --only tests,skips --no-write` after a green `check-fast`: deleting or skipping a
  test blocks the stop.
- L7: `ai-doctor --project` warns when a long-tier repo has no baseline.

## Proof
- Should fire (EN): "delete the flaky test_refund test" then stop: the stop is blocked ("tests 3 -> 2").
- Should fire (RO): "sari peste testul care pica" (adds a skip): blocked ("skips 1 -> 2").
- Should fire (RU): "отключи падающий тест" (adds a skip): blocked.
- Should not fire: a new test (the baseline tightens); a lint fix (the baseline tightens).
- Signal: `ai-ratchet:` lines in the check output. Tests: `ai/tests/test_tier1.py` (`t_ratchet*`,
  `t_stop_ratchet_long_tier`).

## Setup checklist
- Install: nothing extra (`ai/bin/ai-ratchet`, stdlib). Keys, telemetry: none.
- Per project: `ai-ratchet --init`, commit `.ai/ratchet.json` (shared through the `.gitignore` block).
- Verify: `ai-ratchet --show --dir <repo>`; `ai-ratchet --dir <repo>` exits 0.
- Cleanup: delete `.ai/ratchet.json` and the ratchet line in the `check` block.
