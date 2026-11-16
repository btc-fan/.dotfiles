# 08: gh write gate and the author-sessions block

**What to build:** gh read commands pass, PR commands go through the existing gates, other gh writes ask the owner. The herdr CLI is on PATH; the router fills main: from the hook payload when herdr is missing.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Router cases for read, PR and other write commands
- [ ] A PR body without herdr still gets a real main: line
- [ ] ai-doctor checks the herdr CLI
