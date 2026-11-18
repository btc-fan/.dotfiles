# 07: End-to-end scenario with the worktree regression

**What to build:** one `ai-eval` scenario that runs a feature in a fixture repo through a subagent in a linked worktree and shows all 4 hooks: red without the tool or a log, green after a real verify run.

**Blocked by:** 02, 03, 04, 05

**Status:** ready-for-agent

- [ ] The scenario runs headless for Claude; Codex runs the commit-gate part.
- [ ] Each hook goes red once and green once in the report.
- [ ] Report under docs/reports with the date.
