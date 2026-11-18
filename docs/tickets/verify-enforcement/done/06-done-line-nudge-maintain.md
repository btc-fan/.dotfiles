# 06: Done line, nudge per agent, maintain in release

**What to build:** the verify rule reaches every adopted project, each subagent gets the nudge, and the feature map gets a full maintain pass without the owner.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `ai-adopt` adds one managed verify block under a project's own Done section; the owner text stays byte for byte. Projects without a Done section keep the full managed block.
- [x] `verify-before-done` fires once per agent id, not once per session.
- [x] The `release` skill runs `maintain-verification-skill`. A stale status line tells the agent to run it.
