# 17: The router holds only gates, and starts only for a command that a gate names

**What to build:** The hook code holds the gates, the walls and the session start line, and nothing else. It has under 3,000 lines in small modules. Each Claude hook entry has an `if` filter, so the router does not start for a tool call that no gate names. One function answers "is this project adopted".

**Why:** The router has 6,038 lines in 3 files (`router.py` 2,014, `hooklib.py` 3,583, `stop-check.py` 441). After tickets 07, 08, 11, 12 and 13, the reminder code has no rows left: prompt regexes, reminder rendering, the miss log for reminders, the tie-breaks. E2 lists more dead code (list 5, item 7: about 90 lines; item 8: the stop-rule code, about 70 lines). One Bash call starts 7 hook processes over all plugins (README numbers). "Adopted" has 2 definitions: `.ai/enabled` exists, or `.ai/base-version` exists (E2, list 3, item 3). The older ticket `docs/tickets/setup-audit/14-narrow-hook-wiring.md` covers the `if` part; this ticket applies it.

**Solution:**
- Remove each function that has no caller after the 5 tickets. The PR shows a grep or a dead-code tool run for each removed name.
- Remove the dead bits of E2 list 5, items 7 and 8: the stop rules, the Grounded Docs branch, the `quiet_window_s` branch, `PROFILE_AUDIT_GATE`, `hermes_serena_config`, the Linux `caffeinate` shim.
- Split `hooklib.py` by job: shell parsing, one module per gate, state and logs. This prepares ticket 21.
- Test first whether `"if": "Edit(...)"` also matches a `Write` call (file C, section 14, item 1). If not, add one entry with `Write(...)`.
- One `adopted(root)` function in `hooklib`. Each of the 8 readers calls it. The marker is `.ai/enabled`.

**Rules kept:** All 12 gates stay, with their deny texts. The walls `pr-url`, `verify-tool-exists`, `verify-tool-used`, the winner gate and the home-folder deny stay. The merge OK store stays in UserPromptSubmit. No rule loses its home here; this ticket removes code that no rule uses.

**Edge cases:**
1. Codex has no `if` field (file D, section 9). `codex-hooks.json` keeps its matcher `Bash|apply_patch`, and the router filters inside the script.
2. `ask-first` judges many Bash command forms. An `if` cannot hold a list, so the Bash entry stays broad while `ask-first` exists. The `Edit`, `Write`, `Grep` and `Skill` entries get filters.
3. Codex hook trust: a changed `codex-hooks.json` declaration or plugin content needs a new trust in `/hooks` (file D, section 2.9). Until then the hook is skipped and fails open. `ai-sync` runs `codex-trust-hooks`, and `ai-doctor` reports untrusted hooks.
4. The Hermes copy embeds the router and imports `hooklib` by path. The split changes the import paths. If ticket 18 has not moved Hermes out yet, the Hermes plugin imports the new modules, and its test runs.
5. A session that is open during the swap runs the old plugin cache copy until `ai-sync` refreshes it (R-018). The plugin version bump of ticket 16 makes Claude load the new copy.
6. `onFailure: "block"` stays on each PreToolUse entry. A test reads `hooks.json` and fails without it.
7. A plain `ls` must start no router process. A timing test counts processes with a fake router that logs each start.
8. The `if` matching of Bash is best effort: `$()`, backticks and `$VAR` make the hook run anyway (file C, section 3). This only adds runs; it never skips a gate.

**Owner steps:** None.

**Blocked by:** 07, 08, 11, 12, 13

**Status:** ready-for-agent

**Size:** L

- [ ] `wc -l` of the hook Python files is under 3,000 (in the PR).
- [ ] Each removed function has a grep proof of 0 callers in the PR.
- [ ] A test proves whether `if: "Edit(...)"` matches `Write`, and the hook file follows the result.
- [ ] `ai-doctor --numbers` shows the hook processes for one Bash call and for one Read call, before and after.
- [ ] A Read call starts no process of this setup (test).
- [ ] `grep` finds one definition of "adopted", and 0 checks of `.ai/base-version` for that meaning.

**Verify:**
- Unit: `bash ai/tests/run.sh` after each removal commit; new `t_if_filters_present`, `t_on_failure_block` and `t_adopted_one_reader` in `ai/tests/test_setup.py`.
- Drive: `$H drive hook --agent claude PreToolUse` for each gate; `$H drive hook --agent codex PreToolUse` for the `apply_patch` and Bash gates; a real Claude session drive of `git push origin main`.
- Behaviour scenario: all 12 gate scenarios of ticket 02 on Claude, and the Codex set.

**Rollback:** Each removal is its own commit. Revert the one that fails.
