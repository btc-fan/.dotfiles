# 06: Stop check names each high-impact action

**What to build:** when a high-impact command ran in a turn (after an OK), the final reply must name it. Else the Stop hook asks the agent to name each one, so no action stays hidden in a chain.

**Blocked by:** 02

**Status:** done (2026-11-20)

- [x] Stop test: an approved `systemctl restart x` ran and the reply does not name it: block with the list
- [x] The reply names it: pass
- [x] `bash ai/tests/run.sh` 0 failed
