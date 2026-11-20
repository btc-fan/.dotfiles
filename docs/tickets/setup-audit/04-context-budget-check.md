# 04: The setup measures its own fixed context cost

**What to build:** one command reports what the setup loads into each session, and `ai-doctor` warns when a budget is passed. The owner goal is a small always-on context. Today nobody sees the growth.

Measured on 2026-11-18:

- The global `AGENTS.md` is 198 lines and 18.8 KB (about 4.7k tokens). The GUIDE says 2.7k tokens (measured 2026-11-15). The cap in the setup is 30 KB.
- Anthropic's guidance for one instruction file is under 200 lines. Longer files lower how well the agent follows them.
- Three layers shape each reply: the 60-word limit, the i-have-adhd rules and the Ponytail footer. They can ask for different things in one reply.
- The cost table in the GUIDE is stale (OMC skills, total tokens).

**Covered by:** `docs/tickets/rules-that-hold/01-one-command-for-the-numbers.md` builds the report part (`ai-doctor --numbers`).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A command prints, per item, the size at session start: global rules, project rules, each session-start hook text, the skill list, the agent list.
- [ ] `ai-doctor` warns when the global rules pass a budget that the owner sets (lines and bytes), and when the skill list is over its budget.
- [ ] The global rules are checked for text that a hook already enforces. The owner decides what goes out.
- [ ] The cost table in the GUIDE comes from the command, with the date.
