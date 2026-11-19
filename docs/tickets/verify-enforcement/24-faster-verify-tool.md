# 24: Faster verify tool and a verifier subagent (backlog)

**What to build (later):** the verify tool of each project gets cheaper to run, and the ship step gets a check by an agent that did not write the code. Source: `docs/reports/verify-integration-research-2026-11-19.md` (options 1 and 2).

**Blocked by:** owner decision. On 2026-11-19 the owner kept the current approach: measured hook times are 0.16 to 0.46 s, and a full verify run with a real Claude session took 2.6 s.

**Status:** backlog

- [ ] The generator writes `ensure` (reuse the running app, or start it and wait for health), a doctor that checks the running build is the current commit, session reuse, and `verify drive <feature>` that runs all checks of one feature file.
- [ ] The ship skill starts a `verifier` subagent (`skills: [verify-<app>]`, no Edit or Write) that drives the changed features and posts PASS, PASS+NOTES or FAIL on the PR. A verdict stays valid while `git patch-id` is the same.
- [ ] Measure: verify run time before and after on one web project.
