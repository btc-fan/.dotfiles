# writing-for-agents gate (agent documents need the skill first)

Our own gate (`routing.yaml` rule `writing-for-agents`, `require_skill`; code in `router.py` and `hooklib.py`). Added in the
enforcement round of 2026-11-16 (spec `docs/specs/ai-setup-enforcement.md`). The skill: `writing-for-agents` (Matt Pocock).

## Vendor rules (verbatim)
NOT FOUND (our own gate).

## When / when not
- Before an Edit, Write, MultiEdit or Codex `apply_patch` of `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md` or a `SKILL.md`.
- Also before a shell write onto these files: a redirect (`>`, `>>`), `tee`, `sed -i`, `cp` or `mv`.
- Not seen: `python -c`, `perl -i`, `dd`, a script file. The gate stops honest mistakes.
- An edit of other files (README.md) passes.

## Enforcement
- L4 gate (PreToolUse deny). Codex: deny with the message.
- It passes when the session has a proof of the skill: a Skill call, a typed `/writing-for-agents`, or a read of its
  `SKILL.md` from a skill install folder. A vendor copy is no proof. The proof is in the session state.
- Owner skip: `sudo ai-gate-skip writing-for-agents <min> <why>`.
- L1: the skill card names this skill with its trigger.

## Proof
- Should fire (EN): "Add a line to AGENTS.md that says the tests run with make check." The edit is denied until the skill ran.
- Should fire (RO): "Adaugă în AGENTS.md un rând care spune că testele rulează cu make check."
- Should fire (RU): "Добавь в AGENTS.md строку о том, что тесты запускаются через make check."
- Should fire (vague): "write this down" in a repo whose notes live in AGENTS.md (`hard-agent-docs`).
- Should not fire: "Add a line to README.md ..." (`writing-for-agents-not`).
- Signal: `DENY writing-for-agents` in `~/.local/state/ai/gates.log`. Tests: `ai/tests/cases/writing-for-agents.json`,
  eval cases `ai/evals/cases/writing-for-agents*.json` and `hard-agent-docs.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k writing-for-agents`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
