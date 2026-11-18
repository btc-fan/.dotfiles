# 13: Fix the evolution scenario findings

**What to build:** fixes for the findings in `docs/reports/ai-eval-evolution-2026-11-18.md`, then the scenario at 3 of 3 for each agent.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] ai-adopt (or the first session) records `.ai/last-review`, so merge-review fires after the first merge in a new repo
- [ ] The graph is fresh after a commit before the next session starts (or the check waits for the refresh)
- [ ] Codex finishes the first-code step: the writing-for-agents gate must not stop a Map update that the knowledge-check rule asks for
- [ ] `ai-eval scenario --agent both --runs 3`: each step 3 of 3
