# 10: The agent gets a failed check back at the end of its turn

**What to build:** When an agent ends a turn after it changed code files, `stop-check.py` runs `make check-fast` with a time limit. A failure goes back to the agent as its next task. The agent fixes it, or stops after the block cap and tells the owner.

**Why:** Boris Cherny calls a self-check loop his top tip ("2-3x the quality", file F). The spec goal G5 asks for it. `stop-check.py` exists (441 lines), but it does nothing on the `dev-mac` profile: `active_root` returns early when `PROFILE_GUARDS=0`. Every machine runs `dev-mac`. So the code starts a Python process at each SessionStart and Stop, and returns.

Why it is off, from the git history: commit `3250289` (2026-11-15) set `PROFILE_GUARDS=0` in `ai/profiles/dev-mac.env`. Its message says that on each `dev-mac` machine only `secret-scan` and `pr-rules` gate. It turns off `no-sudo`, `no-destroy`, the Stop check and the Claude ask and deny rules, for "full autonomy" (owner, 2026-11-15). So the Stop check went off as part of one autonomy decision, not because of a bug. The same key also switches the Claude ask and deny rules in `claude.sh`.

**Solution:**
- Do not flip `PROFILE_GUARDS`: that would also turn the ask and deny rules on. Add one key `PROFILE_STOP_CHECK=1` for `dev-mac`, read only by `stop-check.py`.
- The check runs only when code files changed in the turn. "Code" uses the one `CODE_EXT` list (today in both `router.py` and `hooklib.py`; this ticket uses the `hooklib` one).
- Time limit 60 s (decision D5). The hook entry timeout goes from 60 s to 75 s, so the hook can report before Claude kills it.
- A timeout passes with a note to the owner, as today. A failure blocks with the command, the exit code and the last 40 lines.
- The block caps stay: 2 blocks on the same tree, 4 in one stop chain (`MAX_TRIES`, `MAX_CHAIN`).

**Rules kept:** "A failing test is a blocker, never pre-existing" (E1 row 68) gets a session check here. CI (ticket 04) is its last wall. The owner's autonomy decision of 2026-11-15 stays for the other guards; only the Stop check changes, by D5. The verify walls (`verify-tool-exists`, `verify-tool-used`) stay as they are.

**Edge cases:**
1. A slow `check-fast` (266 s measured in one project): the 60 s limit kills the process group and passes with a note "check-fast took over 60 s: not run to the end". `ai-doctor --project` names the measured time from the Map check line.
2. A project with no `check-fast` target: silent pass. `ai-doctor --project` reports it.
3. `.ai/enabled` holds `no-stop-check`: the check stays off there. `ai-start` writes this line when `check-fast` fails at adopt time; it keeps doing so.
4. Codex Stop hooks fail open (file D, section 2.6). A Codex crash or timeout lets the turn end. Codex Stop output must be empty or a decision, which `stop-check.py` already respects.
5. Claude Code caps Stop continuations at 8. The script caps at 4 blocks per chain, so the Claude cap is never reached.
6. A red check that the agent did not cause (the test was red at session start): the SessionStart baseline records the tree. When the tree did not change, the check stays silent.
7. Subagents: the check runs on `Stop` only, not on `SubagentStop`. A subagent's change is checked when the main agent ends its turn.
8. An OMC persistent mode is active: the script stays silent, as today. It runs at the first stop after the mode ends.
9. Two Stop hooks can block one stop (the router walls and this check). Each has its own cap; the evidence names both texts.
10. Difference: the timeout note keeps its old text "ran over 60 s and was not judged (counted as a pass)", not the text in edge case 1.
11. Difference: `stop-check.py` is about 470 lines now. Code files dirty before the session are not blamed (a per-file baseline at SessionStart).
12. Difference: a changed root `Makefile` or `justfile` counts as code, so the "recipe changed" block still fires.
13. Difference: the real session drive did not reach the check. The `worktree-first` gate refused the edit on `main` of the fixture.

**Owner steps:** None after D5.

**Blocked by:** 02

**Status:** needs-owner (D5: turn the end-of-turn check on, with a 60 s limit, only when code changed)

**Size:** M

- [x] On `dev-mac`, a turn that breaks a unit test ends with a block that holds the failing test name.
- [x] A turn that changes only Markdown files runs no check (the log shows "no code change").
- [x] A `check-fast` that sleeps 90 s is killed at 60 s and the turn passes with a note.
- [x] `PROFILE_GUARDS` stays `0` on `dev-mac`, and `claude.sh` writes no ask or deny rules.
- [ ] The self-correction scenario of ticket 02 passes on Claude in 3 of 3 runs.

**Verify:**
- Unit: `ai/tests/test_tier1.py` stop-check block runs with `AI_PROFILE=dev-mac` too; add `t_stop_check_dev_mac_on`, `t_stop_check_code_only` and `t_stop_check_timeout_note`.
- Drive: `$H drive hook --agent claude Stop '<payload>'` on a fixture with a red test; then a real session drive on Claude, and a Codex payload drive of Stop.
- Behaviour scenario: the self-correction scenario of ticket 02 (the agent breaks a test, gets the failure, and fixes it).

**Rollback:** Set `PROFILE_STOP_CHECK=0` in `dev-mac.env`. The script returns early again.
