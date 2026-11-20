# 15: One source shapes each reply

**What to build:** The owner's reply rules live in one text. For Claude it is an output style file that the installer writes and sets with the `outputStyle` key. For Codex the same text is one short part of the rules file. The always-on mode of the i-have-adhd plugin and the closing-line rule of ponytail no longer repeat or contradict it.

**Why:** 3 sources shape each reply today: the global rules file (about 244 words of style text), i-have-adhd (1,215 words at each session start) and ponytail (493 words, with a closing-line rule). File I, section D, lists 6 contradictions. Example: "Lead with the answer" against "the first line is the action". Another: "End with one concrete next action" against "End your reply with what you skipped". An output style becomes part of the system prompt, the strongest place for style (file C; spec, section 4.1). The older ticket `docs/tickets/setup-audit/04-context-budget-check.md` named the same 3 layers.

**Solution:**
- First test, then switch. Run the reply-shape scenario of ticket 02 (3 runs) with today's setup and with the output style. Switch only when obedience is not worse (D4).
- `ai/output-styles/owner.md` holds the draft of file I, section D (about 150 words). It covers the answer first, a 60-word limit with its exceptions, numbered steps and a state line. It ends each reply with "Not checked:" then "Next:". It also asks for STE, no preamble and no em dash.
- `claude.sh` links it to `~/.claude/output-styles/owner.md` and sets `"outputStyle": "owner"` through `aiconf` (recorded, so `uninstall.sh` undoes it).
- `claude.sh` stops writing the i-have-adhd always-on flag file, and removes it once. `/i-have-adhd` stays callable (D7: keep 1 source).
- ponytail stays at `full` for its coding rules. Its closing line now agrees with line "Not checked:" of the style. If the plugin has a switch for the closing line, the installer sets it; else the PR says that both ask for the same line.
- `ai-render` puts the same text as the first part of the Codex `AI:core` block. The global file keeps 1 line: "Reply shape: the owner output style."

**Rules kept:** These rules move into the one style text: "Lead with the answer, 60 words", "Follow i-have-adhd", "the state line and the one next action". Also "Documents and PR bodies do not use this shape" and the STE style. The "stop adhd mode" switch stays: the style text names it, and it turns the shape off for the session.

**Edge cases:**
1. Subagents do not get an output style (file C, section 1.5). Ponytail still reaches them through SubagentStart. The style text adds nothing there; the brief of each subagent sets its own report shape.
2. The owner says "stop adhd mode": the style text says to drop the 60-word limit, the state line and the closing lines for the rest of the session. A test reads the style file for the phrase.
3. A plugin update turns its always-on mode on again: `ai-doctor` warns when the i-have-adhd flag file exists, and `install.sh` removes it on each run.
4. Coding tasks: the style must not hide detail. The 60-word limit does not count code blocks, and the owner can ask for detail. The scenario includes a coding question.
5. A project sets its own `outputStyle` in `.claude/settings.json`: the project wins (settings precedence). `ai-doctor --project` reports it.
6. Codex has no output style. Its text is in `~/.codex/AGENTS.md`, under the 32 KiB limit, next to the OMX blocks.
7. Obedience is worse with the style: the ticket stops, keeps today's setup, and writes both rates into the ticket for D4.
8. herdr emoji reactions are not part of this ticket. They stay an owner choice (file I, section E, "Next in line").

**Owner steps:** None after D4 and D7.

**Blocked by:** 02

**Status:** needs-owner (D4: the reply rules move into an output style; D7: keep 1 of the 3 reply sources)

**Size:** M

- [ ] The reply-shape scenario rates before and after are in the PR, 3 runs each.
- [ ] `~/.claude/settings.json` in the dry-run install has `"outputStyle": "owner"`.
- [ ] The install no longer writes the i-have-adhd flag file, and `uninstall.sh` removes the style key.
- [ ] The global rules file has 1 reply-shape line, and the Codex block holds the style text.
- [ ] `ai-doctor --numbers` shows the session-start words before and after (about 1,215 fewer).

**Verify:**
- Unit: `ai/tests/test_setup.py` gets `t_output_style_written` and `t_adhd_flag_removed`; `ai/tests/test_profiles.py` fixtures change.
- Drive: `$H drive install dev-mac` shows the planned files; `$H drive session claude --fixture python-with-tests 'Why is the test slow?'` shows the reply.
- Behaviour scenario: the reply-shape scenario of ticket 02, on Claude and Codex, before and after.

**Rollback:** Remove the `outputStyle` key and the style link; the installer writes the flag file again.
