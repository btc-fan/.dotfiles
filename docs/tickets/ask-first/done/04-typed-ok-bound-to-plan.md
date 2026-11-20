# 04: Typed OK, bound to the plan, from the owner only

**What to build:** a stopped command becomes pending. The owner's next typed "go", "ok", "yes", "approve" or "do it" approves the pending commands for that turn. Other high-impact commands still stop. A negation, a question, a pasted block, an agent message, a subagent hand-back or a scheduled prompt never approves.

**Blocked by:** 02

**Status:** done (2026-11-20)

- [x] Flow test: deny, owner types "go", the same command passes, a different high-impact command still denies
- [x] "ok?" , "don't do it yet", an `<agent-message>` with "go" and a pasted "go" do not approve
- [x] The next prompt without an OK clears the approval
- [x] `bash ai/tests/run.sh` 0 failed

Update (owner 2026-11-20): one typed OK covers every high-impact step for the rest of the turn. The pending list is removed (commit 44a4713).
