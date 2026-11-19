# 13: The secret-scan gate uses the built-in scan only and never dead-ends

**What to build:** a commit or a push on a slow machine is checked and passes when it holds no key. Today the gate
runs gitleaks and then the built-in patterns. gitleaks has a 10 s cap inside an 18 s budget. On 2026-11-18 the
Mac was loaded (load average 313), `gitleaks version` alone took about 43 s, and all 7 secret-scan walls of the
day were timeouts. The deny text sends the agent to the owner (`sudo ai-gate-skip`). On a calm machine the same
gate passes in 0.5 s.

Owner direction (2026-11-18): go back to the earlier way of checking.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Red first: a router case where gitleaks sleeps past its cap and the staged diff is clean. Today: deny.
- [ ] The gate decides with the built-in patterns. It starts no gitleaks process.
- [ ] Each subprocess of the scan counts against one budget. The allow-list for the one approved key is read
  once and cached; today it costs 5 git calls for each scan, outside the budget.
- [ ] When the scan cannot finish, it runs one more time. A second timeout reports "not checked" with the command
  to run by hand. The text does not name a `sudo` step.
- [ ] gitleaks is kept only where no agent hook timeout applies (a `pre-push` git hook or CI), or the installer
  step and its pin are removed. The owner decides which.
- [ ] The test values of ticket 11 of `verify-enforcement` still pass, and a real key shape still blocks.
- [ ] A line in `docs/REGRESSIONS.md`.
