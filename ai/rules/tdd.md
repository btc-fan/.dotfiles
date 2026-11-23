# tdd (tests-first prompts)

Home since rules-that-hold 12 (2026-11-20): the description of the `tdd` skill (Matt Pocock) and 1 index line in
`ai/agents-md/80-tool-catalog.md` (it adds the RO and RU words). The router row `tdd` is gone. History: a stop rule
from 2026-11-16, a hint from 2026-11-18 (as a stop, 1 of 1 block was false). The text below is the old row.

## Vendor rules (verbatim)
NOT FOUND (our own rule).

## When / when not
- A prompt that asks for tests first: tests first, test-first, tdd, red-green, "write the failing test first", and the
  Romanian and Russian forms.
- The prompt context names Matt's `tdd`. The end of the turn is never blocked.
- The OMC skill `oh-my-claudecode:tdd` is a loser in the winner table. A call of it is denied, and it is no proof.

## Enforcement
- L2 hint only (see `diagnosing-bugs.md`). No Stop block, no miss row.
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
