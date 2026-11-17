# tdd stop rule (tests-first prompts)

Our own stop rule (`routing.yaml` rule `tdd`, `strength: stop`, `require_skill`). Added 2026-11-16 by owner decision after
the baseline: Claude worked test-first by hand and used the skill in 0 of 3 runs. The skill: `tdd` (Matt Pocock).

## Vendor rules (verbatim)
NOT FOUND (our own rule).

## When / when not
- A prompt that asks for tests first: tests first, test-first, tdd, red-green, "write the failing test first", and the
  Romanian and Russian forms.
- The turn cannot end before Matt's `tdd` ran. Once per session per rule.
- The OMC skill `oh-my-claudecode:tdd` is a loser in the winner table. A call of it is denied, and it is no proof.

## Enforcement
- L4 stop rule (see `diagnosing-bugs-stop.md`). Owner skip: `sudo ai-gate-skip tdd <min> <why>`.
- Works with the winner gate: the deny of `oh-my-claudecode:tdd` names `tdd`.

## Proof
- Should fire (EN): "Add a discount function, tests first." Should fire (RO): "teste mai intai". Should fire (RU): "сначала тесты".
- Should not fire: a prompt that only says "run the tests".
- Signal: a `misses.jsonl` row for `tdd` when skipped. Tests: `ai/tests/cases/tdd.json`; eval case `winner-tdd`
  (it was 0/3 before this rule; a new run is open in ticket 12).

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k tdd`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
