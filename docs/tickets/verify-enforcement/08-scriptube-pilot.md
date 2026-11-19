# 08: ScripTube pilot

**What to build:** ScripTube runs on the new rules. The AI upgrades `verify-scriptube` with a maintain pass, the project's own test gate (from its PR #13, ADR 0001) is removed, and `ai-adopt` adds the verify Done line.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07

**Status:** ready-for-agent

- [ ] Feature files for Channel Watch, Paused and resume, webhooks and the scheduler exist, with the atlas proof set.
- [ ] The helper writes the log fields the hooks read.
- [ ] The project hook and its settings entry are gone; the ADR records why.
- [ ] One feature driven end to end on the new rules; evidence path in the PR.
- [x] oldmac setup updated to the merged commit first (69ce424, 2026-11-19). The verify Done line is merged in the project (re-adopt PR).
