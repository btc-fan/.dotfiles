# diagnosing-bugs stop rule (bug and performance prompts)

Our own stop rule (`routing.yaml` rule `diagnosing-bugs`, `strength: stop`, `require_skill`). Added 2026-11-16. The skill:
`diagnosing-bugs` (Matt Pocock).

## Vendor rules (verbatim)
NOT FOUND (our own rule). Platform fact: a Claude Stop hook accepts `{"decision": "block", "reason"}`.

## When / when not
- A prompt about a bug or a performance problem: slow, performance, perf, broken, debug, crash, regression, and the
  Romanian and Russian forms. The prompt arms the rule.
- The turn cannot end before the skill ran. The block happens once per session per rule.
- A prompt without these words does not arm it (a question about code, a feature request).

## Enforcement
- L4 stop rule: the next Stop gets `{"decision": "block"}` with the reason, when the session has no proof of the skill.
  Proof: a Skill call, a typed `/diagnosing-bugs`, or a read of its `SKILL.md` from a skill install folder.
- Each block is a row in `~/.local/state/ai/misses.jsonl`. Owner skip: `sudo ai-gate-skip diagnosing-bugs <min> <why>`.
- L1: the skill card names this skill.

## Proof
- Should fire (EN): "The app is slow when I run python3 -m app.cli 2 3. Find out why." (`diagnosing-bugs`).
- Should fire (RO): `diagnosing-bugs-ro`. Should fire (RU): `diagnosing-bugs-ru`.
- Should fire (vague): "investigate how it performs" (`hard-perf`, was 0/3, now 3/3).
- Should not fire: a prompt with no bug word (`diagnosing-bugs-not`).
- Signal: a `misses.jsonl` row for `diagnosing-bugs` when the skill was skipped; `fired.jsonl` kind `skill` when used.
  Tests: `ai/tests/cases/diagnosing-bugs.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k diagnosing-bugs`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
- Behaviour check: `ai-eval behaviour --agent claude --runs 3` (Claude gets 15 turns, so the Stop rule can fire).
