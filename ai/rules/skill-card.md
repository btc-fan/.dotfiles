# skill card (SessionStart: the skills the agent must know)

Our own context (`routing.yaml` block `skills:`; code `skill_card` in `router.py`). Added 2026-11-16. Reason: 10 required
skills are typed-only (`disable-model-invocation`), so the agent did not see them; 3 skill uses in 7 days.

## Vendor rules (verbatim)
NOT FOUND (our own context).

## When / when not
- At every SessionStart: startup, resume, clear and compact. Under 1500 characters; `ai-render` fails above that.
- Must-use skills with one trigger line: `writing-for-agents`, `diagnosing-bugs`, `ship`, `tdd`.
- Typed-only skills: `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `handoff`, `wayfinder`,
  `improve-codebase-architecture`, `retro`. For these the card says:
  read `<SKILL.md>` and follow it, and tell the owner the typed form.
- Only typed-only skills that are installed get a folder in the card.

## Enforcement
- L1 context. No deny. The gates and stop rules of the must-use skills are the L4 part.
- Skill use is logged to `fired.jsonl` (kind `skill`): a Skill call, a typed `/name`, a read of a `SKILL.md`.
  `ai-doctor` counts it over 30 days. A read counts only from a skill install folder.

## Proof
- Should fire: every new, resumed, cleared or compacted session shows the card.
- Should not fire: a project's own `ai/skills/<name>/SKILL.md` read is not a proof.
- Signal: the card text in the SessionStart context. Tests: `ai/tests/cases/_skill-card.json`, `_proof.json`.
- Limit: after `/compact` or `/clear` the SessionStart text is about 10.1k characters; the L0 table tail is cut at 9.5k there.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k skill`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
