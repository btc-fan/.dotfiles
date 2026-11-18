# 11: Evolution test from an empty repo

**What to build:** a multi-session scenario: empty repo, first code, feature, PR, merge, next session. The Map is updated, the graph refreshes after the commit, the next session uses graphify and Serena on the new code, and the merge-review prompt fires.

**Blocked by:** 06, 07, 09

**Status:** ready-for-agent

- [x] Scenario runs headless for Claude and for Codex (`ai-eval scenario`, report docs/reports/ai-eval-evolution-2026-11-18.md)
- [ ] Each check passes in 3 of 3 runs: not yet, findings moved to ticket 13
