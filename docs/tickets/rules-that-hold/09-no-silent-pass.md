# 09: A missing check tool fails, and never passes in silence

**What to build:** When the git pre-commit hook cannot find `ai-precommit`, the commit fails with a message that says how to fix it. When `make check` runs in CI and a setup tool is missing, the target fails. Today both print "skipped" and exit 0.

**Why:** The pre-commit hook that `ai-adopt` writes (`PRECOMMIT_HOOK` in `ai-start`) says "ai-precommit not on PATH: pre-commit check skipped" and exits 0. The Makefile block (`ai-check-detect`: `RATCHET_LINE`, `LEDGER_LINE`, `DOCS_LINE`, `MD_LINE`) prints "not on PATH: ... skipped" and passes. In CI this means a green check with no check (E1, Task 3; spec, section 10, item 6: "Do not trust a check that can pass silently").

**Solution:**
- The pre-commit hook exits 1 when `ai-precommit` is not found. The message names the fix: run `install.sh`, or add the setup's `bin` folder to PATH for this git client.
- The owner's escape: the git config key `ai.precommit` set to `optional` in that clone. The hook then prints one warning line and passes. Only a person sets it; the message says so.
- The Makefile lines fail when `CI` is set and the tool is missing. Outside CI they keep the skip line, with the word `WARN` in front.
- `ai-adopt` rewrites an old hook that it wrote (same marker line). It never touches a hook that it did not write.
- `ai-doctor --project` reports an adopted project whose hook is the old silent version.

**Rules kept:** "A failing test is a blocker" and "never trust a silent pass" (E1 row 68, spec section 10) get a check here. The `verify-commit` wall inside `ai-precommit` stays as it is; it now cannot be skipped by a short PATH.

**Edge cases:**
1. A machine without the setup clones an adopted project: `.git/hooks` is not part of a clone, so that clone has no hook at all. Conflict with the outline: the hook cannot help there. CI (tickets 04 and 06) covers that case.
2. The real case for the hook: the setup is installed, but a GUI git client or an IDE runs git with a short PATH. The message names the tool and the PATH that the hook saw.
3. Existing owner hooks: `ai-adopt` installs no hook when the repo has its own `pre-commit` file or `core.hooksPath` (husky, lefthook, pre-commit). This stays. `ai-adopt` prints the line to add to those hooks.
4. Husky runs hooks with `sh` and its own PATH setup. The printed line uses `command -v` and the same failure text, so it behaves the same.
5. `CI` set on a local machine by hand: the target then fails on a missing tool. This is wanted: the variable means "no skip".
6. An agent sets `ai.precommit=optional` to pass the hook. The setting is visible in `git config --list`, and `ai-doctor --project` reports it as WARN.
7. An old adopted project with the silent hook: the next `ai-adopt` run updates it. `ai-doctor` names each project that still has it.
8. Linux and macOS: the hook uses `/bin/sh` and `command -v` only.
9. Code fact: the old Makefile lines stayed after a rerun, because the block merge kept them as owner lines. `ai-check-detect` now maps each old line to its new line.
10. Code fact: the Makefile lines read `CI` with `printenv CI`, not `$CI`. The same text then works in a Makefile and a justfile.
11. Code fact: the commit of `ai-adopt` runs the new hook. That commit puts the bin folder of `ai-adopt` first in PATH.

**Owner steps:** None.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** S

- [x] In a fixture with PATH that has no `ai-precommit`, `git commit` exits 1, and the message names `install.sh`.
- [x] With `git config ai.precommit optional`, the same commit passes with one warning line.
- [x] `CI=1 make check` fails in a fixture where `ai-docs-check` is not on PATH.
- [x] `make check` without `CI` prints a `WARN` line for the missing tool and passes.
- [x] `ai-doctor --project` names a project with the old silent hook.

**Verify:**
- Unit: `ai/tests/test_tier1.py` gets `t_precommit_hook_missing_tool`, `t_precommit_optional_key`, `t_make_check_ci_missing_tool` and `t_adopt_upgrades_silent_checks`.
- Drive: `$H drive cli --fixture python-with-tests ai-adopt`, then a real `git commit` with a short PATH, and `CI=1 make check` in the fixture.
- Behaviour scenario: `gate-secret-scan` and `gate-no-verify` of ticket 02 still pass.

**Rollback:** Revert. The hook text and the Makefile lines go back to the skip lines.
