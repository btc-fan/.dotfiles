# tdd hint (tests-first prompts; a stop rule until 2026-11-18)

Our own rule (`routing.yaml` rule `tdd`, `strength: nudge`). Added 2026-11-16 as a stop rule by owner decision after
the baseline: Claude worked test-first by hand and used the skill in 0 of 3 runs. Since 2026-11-18 (ticket 14) it is a
hint: as a stop, 1 of 1 block was false. The skill: `tdd` (Matt Pocock).

## Vendor rules (verbatim)
NOT FOUND (our own rule).

## When / when not
- A prompt that asks for tests first: tests first, test-first, tdd, red-green, "write the failing test first", and the
  Romanian and Russian forms.
- The prompt context names Matt's `tdd`. The end of the turn is never blocked.
- The OMC skill `oh-my-claudecode:tdd` is a loser in the winner table. A call of it is denied, and it is no proof.

## Enforcement
- L2 hint only (see `diagnosing-bugs-stop.md`). No Stop block, no miss row.
- Works with the winner gate: the deny of `oh-my-claudecode:tdd` names `tdd`.

## Proof
- Should fire (EN): "Add a discount function, tests first." Should fire (RO): "teste mai intai". Should fire (RU): "сначала тесты".
- Should not fire: a prompt that only says "run the tests".
- Signal: a `fired.jsonl` row (kind `rule`) when the hint fires. Tests: `ai/tests/cases/tdd.json`; eval case `winner-tdd`
  (it was 0/3 before this rule; a new run is open in ticket 12).

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k tdd`; `ai-doctor` shows the skill use of the last 30 days.
- Cleanup: none (the rule is part of the router).
