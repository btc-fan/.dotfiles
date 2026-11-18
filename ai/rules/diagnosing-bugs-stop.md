# diagnosing-bugs hint (bug and performance prompts; a stop rule until 2026-11-18)

Our own rule (`routing.yaml` rule `diagnosing-bugs`, `strength: nudge`). Added 2026-11-16 as a stop rule. Since
2026-11-18 (ticket 14) it is a hint: as a stop, 6 of 6 blocks were false (research and setup prompts that mention
debug, broken or crash). The skill: `diagnosing-bugs` (Matt Pocock).

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
