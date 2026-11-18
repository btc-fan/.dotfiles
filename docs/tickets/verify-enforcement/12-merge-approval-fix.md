# 12: merge-approval reads the owner's OK and the real target branch

**What to build:** the gate still blocks a merge or a push to main without the owner's OK, but it accepts the ways the owner says it and checks the branch the command acts on. Measured: 17 blocks in 7 days, 14 false.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Accepted: "merge 18", "merge #18", "merge the branches", "merge everything", "lets merge everything", "lets merge this". Refused stays refused: "don't merge", "not yet", "wait".
- [ ] The push check reads the branch of the checkout the command acts on (`cd <dir> &&`, `git -C <dir>`), not the session folder.
- [ ] A command that only contains the word main (for example `git diff main...HEAD`) is not a push to main.
- [ ] Cases for each missed OK from the 7-day log.
