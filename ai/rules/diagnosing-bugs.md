# diagnosing-bugs (bug and performance prompts)

Home since rules-that-hold 12 (2026-11-20): the description of the `diagnosing-bugs` skill (Matt Pocock) and 1 index
line in `ai/agents-md/80-tool-catalog.md` (it adds crash, regression and the RO and RU words). The router row is
gone. History: a stop rule from 2026-11-16, a hint from 2026-11-18 (as a stop, 6 of 6 blocks were false). The text
below is the old row.

## Vendor rules (verbatim)
NOT FOUND (our own rule). Platform fact: a Claude Stop hook accepts `{"decision": "block", "reason"}`.

## When / when not
- A prompt about a bug or a performance problem: slow, performance, perf, broken, debug, crash, regression, and the
  Romanian and Russian forms. The prompt context shows the hint.
- The end of the turn is never blocked.
- A prompt without these words does not arm it (a question about code, a feature request).

## Enforcement
- L2 hint only: the UserPromptSubmit context names the skill. No Stop block, no miss row.
- L1: the skill card names this skill under the hint skills.

## Proof
- Should fire (EN): "The app is slow when I run python3 -m app.cli 2 3. Find out why." (`diagnosing-bugs`).
- Should fire (RO): `diagnosing-bugs-ro`. Should fire (RU): `diagnosing-bugs-ru`.
- Should fire (vague): "investigate how it performs" (`hard-perf`, was 0/3, now 3/3).
- Should not fire: a prompt with no bug word (`diagnosing-bugs-not`).
- Should not block: a research turn that mentions debug or broken ends without a block.
- Signal: a `fired.jsonl` row (kind `rule`) when the hint fires; `fired.jsonl` kind `skill` when the skill is used.
  Tests: `ai/tests/cases/diagnosing-bugs.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k diagnosing-bugs`; `ai-doctor` shows the skill use of the last 30 days.
- Cleanup: none (the rule is part of the router).
- Behaviour check: `ai-eval behaviour --agent claude --runs 3` (the case expects the skill and the rule).
