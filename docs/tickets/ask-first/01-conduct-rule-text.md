# 01: Conduct rule text for every agent

**What to build:** every Claude and Codex session loads the new "Standing permission" text (spec Part 1). It names the high-impact steps, says "show the plan, the risk and the undo, then wait", and defines "prepare", "audit" and a question. The draft PR rule opens a PR only when the owner asked for feature or fix work. This repo's full-rights project rule changes to the middle way.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The rendered `~/.config/ai/AGENTS.md` and the Codex block have the new text (`ai-render`, fixture tests updated)
- [ ] The git-workflow rule opens a draft PR only on an owner ask for feature or fix work
- [ ] This repo's AGENTS.md project rule: feature branch push is free; a merge to `ai` and a machine install wait for the owner (writing-for-agents loaded first)
- [ ] No sentence over 25 words, no em dash; `bash ai/tests/run.sh` 0 failed
