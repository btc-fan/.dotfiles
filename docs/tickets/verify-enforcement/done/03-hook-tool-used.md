# 03: Hook 2, the verify tool must be used

**What to build:** when an agent changed app code in its checkout and made no new valid tool log since the change, its turn cannot end (Stop and SubagentStop). The change is read from git in the agent's own checkout, so shell writes and worktrees count. This ticket also adds the shared log reader: a log is valid when doctor passed and the run made no direct DB writes.

**Blocked by:** 01

**Status:** done

- [x] Red: app code changed through a shell write in a linked worktree, no new log: blocked. This is the ScripTube regression.
- [x] Green: a valid log newer than the first change: the turn ends.
- [x] Invalid logs do not count: doctor FAIL, or a direct DB write in the run.
- [x] The stop loop limit still applies (no endless block).
