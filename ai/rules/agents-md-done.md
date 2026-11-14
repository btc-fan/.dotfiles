# Done and Lessons sections of the repo AGENTS.md (size budget)

Our own template (Tier 1 T5). Text from the owner plan (project-evolution research B1, B3).

## Vendor rules (verbatim)
NOT FOUND (our own template).

## When / when not
- `ai-adopt` adds a managed `## Done` block (6 numbered lines, between `<!-- AI:done START` and
  `<!-- AI:done END -->`) and a `## Lessons` section (agents add lines; at most 15).
- A repo with its own `## Done` (or "Definition of done") section keeps it; no second one is added (ai-adopt
  says so).
- The Done text follows the tier: item 2 names `docs/REGRESSIONS.md` in long-tier projects.
- Lessons: one line per repeated mistake that no check catches yet; delete the line when a check covers it.
- Code Review Rules section: not added (owner plan section 11: only in repos that use Codex `/review` or GitHub
  review).

## Enforcement
- L0: the sections are in the repo AGENTS.md, read in every session.
- Checks: the stop hook and the PR gate check items 1, 2 and 6 where a machine can.
- L7: `ai-doctor --project`: repo AGENTS.md size (warn above 12 KB), root rules + repo file under 32 KiB (Codex
  stops reading after that: FAIL), Done at most 6 lines, Lessons at most 15 lines.

## Proof
- Should fire (EN): `ai-adopt` in a repo without a Done section adds the block.
- Should fire (RO): "adauga sectiunea Done in AGENTS.md" (the agent runs ai-adopt, not a hand copy).
- Should fire (RU): "добавь раздел Done в AGENTS.md" (the agent runs ai-adopt).
- Should not fire: a repo with a hand-written `## Done`; a rerun (nothing changes).
- Signal: the block markers in AGENTS.md; `ai-doctor --project` lines. Tests: `ai/tests/test_tier1.py`
  (`t_adopt_try_tier_own_done`, `t_doctor_budget`), `test_knowledge.py`.

## Setup checklist
- Install: nothing extra (ai-adopt). Keys, telemetry: none.
- Per project: `ai-adopt`; trim Lessons when ai-doctor warns.
- Verify: `ai-doctor --project <repo>`.
- Cleanup: delete the block between the markers and the Lessons section.
