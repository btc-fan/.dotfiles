# ship gate (gh pr ready needs the ship skill)

Our own gate (`routing.yaml` rule `ship`, `require_skill`). Added 2026-11-16. The skill: `ship` (ours,
`ai/skills/ship/SKILL.md`).

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
- `gh pr ready` is denied until the `ship` skill ran in the session (checks, review, Evidence).
- `gh pr ready --undo` passes. `gh pr create`, `edit`, `merge` have their own gates (pr-rules, merge-approval).
- Also behind `rtk`, `env`, `bash -c`.

## Enforcement
- L4 gate. Codex: deny with the message. Proof: a Skill call, a typed `/ship`, or a read of its `SKILL.md`.
- Owner skip: `sudo ai-gate-skip ship <min> <why>`.
- L1: the skill card names `ship` ("the branch is done, before gh pr ready").

## Proof
- Should fire (EN): `ship` ("ship it", Claude 1/3 before, 3/3 after). RO: `ship-ro`. RU: `ship-ru`.
- Should fire (vague): "ok this is good, wrap it up for review" (`hard-ship`, was 0/3, now 3/3).
- Should not fire: `ship-not`; `gh pr ready --undo`.
- Signal: `DENY ship` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/ship.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k ship`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
