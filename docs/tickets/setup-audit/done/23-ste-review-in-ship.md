# 23: The ship skill checks the PR text against STE

**What to build:** the ship skill has a step before `gh pr ready`. The agent reads the PR body and the changed
documents, and rewrites each sentence that breaks an ASD-STE100 rule.

**Blocked by:** None (can start immediately)

**Status:** done (2026-11-19)

Why: the `ste-sentence` rule (ticket 21) checks only the length of new Markdown sentences. The other STE rules
(one instruction per sentence, active voice, approved words) have no check.

- [x] A new part of step 8 in `ai/skills/ship/SKILL.md`, before `gh pr ready` (no new step number). Load the writing-for-agents skill before the edit.
- [x] The step names the rules to check and ends on a clear done condition.
- [x] Not in scope: a Vale word list. It needs a new tool, and the length check plus this step cover most of STE.
