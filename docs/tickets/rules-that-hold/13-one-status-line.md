# 13: One status line at session start

**What to build:** At session start, the router sends one status line of under 60 words: the Map and Libraries state, Serena on or off, the graph state, and the opt-in tools. The rows `project-knowledge`, `serena` and `graph` become this one line. After a compaction or a `/clear`, the router does not send the rule table again. The author-sessions line stays.

**Why:** E1 gives these 3 rows the verdict KEEP-AS-SESSION-FACT: the facts are useful, but 3 rows say them in 3 places. The router sends the L0 table again on `compact` and `clear` (`L0_RESEND_SOURCES`), so the table loads twice in a long session. The rules file already loads after a compaction from disk (file C, section 1.4). Spec section 6.9 sets the target: 1 status line, under 60 words.

**Solution:**
- One function builds the line from the `{knowledge_index}` data and `.ai/enabled`. Example: `ai: Map ok, Libraries 4 (fresh), Serena on, graph fresh, opt-in: ui.`
- The 3 rows go from `ai/routing.yaml`. The line is a fixed part of the SessionStart handler, not a rule. It is a fact, so it holds no instruction.
- `L0_RESEND_SOURCES` goes. On `compact` and `clear` the router sends the same status line and the sessions line, and nothing more.
- The author-sessions line (`SESSION_MSG`: the session id for the PR block) stays as its own line.
- The skill card stays in this ticket. Ticket 14 removes its copy in the rules file and decides its final form.
- `ai-render` fails when the worst-case status line has more than 60 words.

**Rules kept:** "The Map is the first place to look" stays: `@AGENTS.md` loads the Map in each session (E1 row 37). "Use Serena for symbols, graphify for wide questions" stays as 1 line in the rules file (E1 rows 38 to 41). The status line gives the on or off fact. The `nav-first` gate is not touched here.

**Edge cases:**
1. A project with no Map: the line says "Map: none". It does not say "run ai-adopt"; that home is `ai-doctor` (ticket 11).
2. Serena or graph off (`no-serena`, `no-graph` in `.ai/enabled`): the line says "Serena off" or "graph off". A test covers each value.
3. A repo that is not adopted: the line is "ai: not adopted". It is a fact of 3 words.
4. The skill card is also SessionStart text, under 1,500 characters. Conflict with the outline: the card and the status line together are over 60 words. The ticket reports both counts, and ticket 14 shrinks the card.
5. The 10,000-character cap on `additionalContext` (file C, section 2.4): the whole start text stays far under it. A test asserts under 2,000 characters.
6. Explore and Plan subagents load no rules files. SessionStart text reaches the main session only. No subagent needs the status line, so this ticket adds no SubagentStart text.
7. A session that is open during the change gets the new line at its next compaction. Its old L0 text stays in context until then.
8. Codex: the same router runs on Codex SessionStart. Codex has no `compact` source in the same form, so the test sends `startup` and `resume` for Codex.

**Owner steps:** None.

**Blocked by:** 11

**Status:** ready-for-agent

**Size:** S

- [ ] A SessionStart payload with `source: startup` gives 1 status line under 60 words, plus the sessions line and the card.
- [ ] A payload with `source: compact` gives no L0 table.
- [ ] `ai/routing.yaml` has no rows `project-knowledge`, `serena` and `graph`.
- [ ] The line is right for 4 fixtures: no Map, Serena off, graph off, not adopted.
- [ ] `ai-render` fails on a status template that can pass 60 words.
- [ ] `ai-doctor --numbers` shows the start text of this setup before and after.

**Verify:**
- Unit: `ai/tests/cases/_home-folder.json` and `_skill-card.json` still pass; new cases in `ai/tests/cases/_status-line.json` for the 4 fixtures and for `compact`.
- Drive: `$H drive hook --agent claude SessionStart '{"source":"compact",...}'` and the same for codex with `startup`; a real Claude session drive that prints its start context.
- Behaviour scenario: the navigation scenario of ticket 02, to see that Serena and graph use did not drop.

**Rollback:** Revert. The 3 rows and the L0 resend come back.
