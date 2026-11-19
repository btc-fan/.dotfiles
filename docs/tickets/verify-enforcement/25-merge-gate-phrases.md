# 25: Merge gate misses "merge then continue"

**What to build:** the merge-approval gate accepts an owner message that starts with "merge" and goes on with a next step ("merge then continue", "merge and go on"), and still refuses a negation ("don't merge then continue").

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Seen 2026-11-19: the owner wrote "merge then continue"; the gate denied `gh pr merge`; the owner had to write "merge" alone. Same class as R-009 ("merge go ahead").

- [ ] Red: a case in `ai/tests/cases/` with "merge then continue" expects allow; a case with "don't merge then continue" expects deny.
- [ ] Green: `MERGE_OK_RX` in `hooklib.py` accepts the phrase; every existing merge-approval case still passes.
- [ ] A line in `docs/REGRESSIONS.md`.
