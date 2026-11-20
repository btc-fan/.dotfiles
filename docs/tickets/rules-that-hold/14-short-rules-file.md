# 14: The always-loaded rules file has under 600 words and works as an index

**What to build:** The global rules file that each session loads has under 600 words on each profile. It holds the reply shape, or 1 line that names the output style. It holds the facts that an agent cannot find. It holds an index with 1 line per skill, doc and check command. It ends with the short list of hard rules, each with the name of its check. The rule table is gone from it. `ai-render` fails above the new size plus 10%.

**Why:** The file has 218 lines and 3,460 words; the rule table in it has 1,088 words (spec, section 2). `docs/AGENTS-MD.md` gives a target of 12 KB, and the file has 19 KB to 21 KB. E1, Task 1, sorts its 153 rows: 41 stay as text, 60 are copies, 21 are procedures for a skill, 13 get a check, 18 are stale. The fixed cost of a Claude session is about 22,790 tokens, and the rules files are 5,151 of them (file I, section B).

**Solution:**
- First, a list file for the owner: `docs/tickets/rules-that-hold/14-keep-list.md`. One row per E1 row: id, text, verdict, home, and an empty keep mark. The owner marks the rows to keep (D3, step M4).
- Then cut, by verdict: delete MERGE and DELETE rows, move MOVE-TO-SKILL rows into the named skill, keep KEEP-TEXT rows and each row the owner marked.
- Remove the L0 table part (`85-l0.md`) from the always-loaded file. The gates print their own text when they deny.
- Add the index: 1 line per skill, doc and check command that the removed text pointed to, with the condition for its use.
- Lower `AGENTS_CAP` in `ai-render` from 30 KB to the new size plus 10%. The docs that name "30 KB" name the constant instead.
- `ai-start` writes the guidance of "Lessons" and "Project rules" as 1 visible line each. Claude Code strips HTML comments, so the model never saw the old guidance.

**Rules kept:**
- KEEP-TEXT rows (41, 471 words) stay in the file. MERGE rows stay in the home that E1 names (a gate message, a skill, a project doc).
- MOVE-TO-SKILL rows go into `ship`, `pr`, `writing-for-agents`, `skills-guide` and the `CODING_STANDARDS.md` template, with 1 index line each.
- MOVE-TO-CHECK rows with a check from tickets 07 and 08 (em dash, Map, Libraries, memory) go. The other MOVE-TO-CHECK rows have no ticket (`git add -A`, `claude -p --bare`, `.env` reads, a PR from `prototype/`, secrets in a docs query). They stay as text, and the keep list says so.
- Each owner row with a keep mark stays, whatever its verdict.

**Edge cases:**
1. The Codex copy: Codex has no `@` import and a 32 KiB limit (file D, section 1). `ai-sync` writes the block `AI:core` into `~/.codex/AGENTS.md`. The same short text goes there, and the OMX blocks in that file are not touched.
2. The server profile render: both renders must be under the cap. `ai-render --profile server --check` runs in the suite until ticket 18.
3. The golden fixtures (`agents-server.md`, `agents-dev-mac.md`) change in the same commit.
4. A skill without an index line: a test lists each model-invocable skill of this setup and fails when the file has no line for it.
5. An index line for a skill that is not installed in a project (an opt-in tool): the line says "when on in `.ai/enabled`".
6. The skill card of ticket 13 repeats the must-use skills. The index holds them once; the card keeps only what the gates need.
7. The owner does not mark the list: the ticket waits. No row with an empty keep mark is cut before step M4.
8. A second machine that is behind keeps the long file until its `ai-sync`. Nothing breaks.

**Owner steps:** M4: mark the rows to keep in `docs/tickets/rules-that-hold/14-keep-list.md`.

**Blocked by:** 07, 08, 11, 12, 13

**Status:** needs-owner (D3: which of the owner's own text lines leave the always-loaded file)

**Size:** L

- [ ] `14-keep-list.md` exists with 153 rows and the owner's marks.
- [ ] The rendered global file has under 600 words on `dev-mac` and on `server` (`wc -w` in the PR).
- [ ] The file has no rule table and no procedure of more than 2 lines.
- [ ] `ai-render` fails when a part pushes the file over the new cap (test).
- [ ] Each model-invocable skill of this setup has 1 index line (test).
- [ ] A new adopted project shows the "Lessons" and "Project rules" guidance as visible text.

**Verify:**
- Unit: `ai/tests/test_commands.py` gets `t_agents_cap_lowered` and `t_index_has_each_skill`; the golden fixtures change.
- Drive: `$H drive install dev-mac` shows the new size; `$H drive session claude --fixture python-with-tests 'ship it'` shows the skill opened from its index line.
- Behaviour scenario: the 12 gate scenarios and the reply-shape scenario of ticket 02, before and after.

**Rollback:** Revert. The text parts are plain files; the cap goes back with them.
