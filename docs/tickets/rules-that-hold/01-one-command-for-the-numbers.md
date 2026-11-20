# 01: One command prints the fixed cost and the obedience numbers

**What to build:** The owner runs `ai-doctor --numbers` and sees what a new session costs before work starts. It also sees how often the rules held in the last 7 days. `ai-doctor --numbers --json` prints the same numbers for a script. The first run is saved as `docs/reports/baseline-<date>.md`. Each later ticket compares its result with this file.

**Why:** Today nobody sees the fixed cost without a hand count. File I, section B, counted it by hand: about 14,330 words, about 22,790 tokens for one new Claude session. The spec numbers (321 reminder fires, 241 not followed, 50 hook commands) came from a one-off script. `ai-doctor` already reads `fired.jsonl`, `misses.jsonl` and `walls.jsonl` for 7 days (`report_logs`, `report_walls`), so the data sources exist. The older ticket `docs/tickets/setup-audit/04-context-budget-check.md` asks for the same command. This ticket covers it.

**Solution:**
- Extend `ai-doctor`, not `ai-info`. `ai-doctor` already reads the logs. `ai-info` lists what the machine offers and must stay fast.
- The new mode `--numbers` runs no check and always exits 0. A report is not a check.
- Section 1: the words of each rules file (global, Codex copy, project `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md`).
- Section 2: the text added at session start, per hook. Section 3: the hook commands per event and per owner.
- Section 4: the words of skill, agent and MCP descriptions. Section 5: gate denies, and repeated denies of one command.
- Section 6: the reminder fires and misses per rule.
- The session-start text comes from the newest Claude transcript of the project (the hook output records), as file I did. The command never runs a hook of another plugin.
- Tokens are words x 1.4, labelled "estimate". A number that cannot be measured prints "not measured", never 0.
- The JSON has a `version` key, one object per section, and the commit of the setup checkout.

**Rules kept:** No owner rule is touched. The command reads the rules files and the logs. It changes no file outside `docs/reports/`.

**Edge cases:**
1. No logs (a new machine, an empty state folder): each count prints 0 with the mark "no log". The command does not crash.
2. Test runs in the logs: `ai-eval` sets `AI_STATE_DIR` to a run folder, but older runs and verify drives left rows with a temp `cwd`. Rows whose `cwd` is under the system temp folder or a `.verify` run folder are left out. The report prints how many.
3. Other plugins' hooks: read only. A SessionStart hook of another plugin can write state (OMC) or start a process (`caffeinate`). So the command reads transcripts and hook files, and never runs them.
4. No transcript for the project (a new project, or Claude never ran there): the start-text section prints "not measured" and names the reason.
5. Codex: `codex exec --json` drops hook events (file D, section 2.10). The Codex column shows the words of `~/.codex/AGENTS.md`, the Codex hook commands and the Codex rows of the logs (field `agent`). Codex start text prints "not measured".
6. Rotated logs: read `walls.jsonl.1`, `fired.jsonl.1` and `misses.jsonl.1` too, as `report_walls` does.
7. A project that is not adopted: the project rows print "not adopted"; the global rows still print.
8. Linux and macOS: word counts and file reads are in Python stdlib (3.9 works). No `wc`, no `stat` flags that differ.

**Owner steps:** None.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** M

- [ ] `ai-doctor --numbers` prints the 6 sections and exits 0, also when plain `ai-doctor` has a FAIL.
- [ ] `ai-doctor --numbers --json` prints valid JSON with the same numbers.
- [ ] On fixture logs, each count matches the count that the test file states.
- [ ] Rows from temp folders are left out, and the report prints how many.
- [ ] `docs/reports/baseline-<date>.md` exists. It names the commit, and it holds each number of the README table "Numbers that the final ticket must show" that the command can measure.
- [ ] Each number that the command cannot measure prints "not measured" with a reason.
- [ ] The older ticket `docs/tickets/setup-audit/04-context-budget-check.md` has one line that points to this ticket.

**Verify:**
- Unit: add `t_numbers_fixture_logs`, `t_numbers_temp_rows_left_out`, `t_numbers_no_logs` and `t_numbers_json_schema` to `ai/tests/test_info.py`, with fixture log files.
- Drive: `$H launch --label numbers python-with-tests`, then `$H drive cli --fixture python-with-tests ai-doctor --numbers` and the same with `--json`. Keep both outputs in the evidence folder.
- Behaviour scenario: none. This ticket changes no agent behaviour.

**Rollback:** Remove the `--numbers` mode and its tests. Nothing reads it before ticket 23.
