# winner gate (overlapping skills: the winner runs)

Our own gate (`routing.yaml` block `winners:`; code `winner_gate` in `router.py`). Added 2026-11-16. The table is section 5
of `ai/skills/skills-guide/SKILL.md` as data.

## Vendor rules (verbatim)
NOT FOUND (our own gate). Background: OMC adds about 85 and OMX about 24 skills that do the jobs of ours.
`skillOverrides` cannot hide plugin skills.

## When / when not
- A Skill tool call of a loser in `winners.table` is denied with the winner's name. Losers: `oh-my-claudecode:` plan,
  omc-plan, ralplan, execute, tdd, research, review, omc-review, pr, wiki, release; `oh-my-codex:` plan, ralplan,
  best-practice-research, code-review, wiki.
- A typed-only winner (no Skill tool): the deny says "read <SKILL.md path> and follow it".
- Orchestration skills pass (`autopilot`, `ralph`, `team`, `ultragoal`). After one of them ran, the losers pass for the
  session. `ask`, `babysit`, `fix-ci`, `cancel` pass and unlock nothing.
- A typed `/name` never reaches the Skill tool, so the owner's choice always runs.
- Claude only on the Skill tool. Codex: a shell read of a losing skill file (`~/.codex/skills/<name>/SKILL.md` or a
  SKILL.md in an `oh-my-claudecode` folder) is denied the same way.

## Enforcement
- L4 gate, also in a subagent. Owner skip: `sudo ai-gate-skip winner-gate <min> <why>`.
- `ai/tests/test_commands.py` keeps the skills guide table and the `winners:` data equal.

## Proof
- Should fire: a Skill call of `oh-my-claudecode:tdd` (eval `winner-tdd`), `oh-my-claudecode:plan`, `oh-my-claudecode:review`.
- Should not fire: a Skill call of the winner (`tdd`); `oh-my-claudecode:autopilot`; a typed `/oh-my-claudecode:plan`.
- Signal: `DENY winner-gate` in `gates.log`. Tests: `ai/tests/cases/_winners.json`.

## Setup checklist
- Install: part of the ai-core router (no extra files). Keys, telemetry: none.
- Verify: `bash ai/tests/run.sh -k winner`; `ai-doctor` shows the misses of the last 30 days.
- Cleanup: none (the rule is part of the router).
- Add a row: `docs/EXTENDING.md`, section 4.2.
