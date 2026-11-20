# 19: One config file holds each owner value, and no tracked file names a local thing

**What to build:** Each value that belongs to one owner lives in one config file. Each other file reads it. Tests, fixtures and docs use neutral names. A test fails when a tracked line holds a name from a deny list in the config. Another person can use the repo with no code edit.

**Why:** 124 tracked lines hold a local name, and 42 of them must change for another user (spec, section 6, Phase 6). E2, list 4, names each place. Examples: local project names in tests, a machine name in `test_setup.py`, and home paths in committed verify evidence. Also `/usr/bin/python3` in 19 hook lines, and the projects folder in 2 places. Today the owner values sit in 5 files under `~/.config/ai/`. Two skills (`promote-skill`, `upgrade-review`) name a folder that does not exist on another machine.

**Solution:**
- `ai/config.defaults.env` in the repo holds generic defaults. `~/.config/ai/config.env` holds the owner values. One shell reader and one Python reader. Secrets stay in `secrets.env`.
- Keys: `AI_PYTHON`, `AI_GITHUB_OWNERS`, `AI_PROMPT_LANGS`, `AI_PROJECTS_DIR`, `AI_BASE_DIR`, `AI_MACHINES`, `AI_PROTECTED_BRANCHES`, `AI_NAME_DENY` (the deny list).
- The hook files get `AI_PYTHON` at render time. The default is `/usr/bin/python3`, because macOS ships Python 3.9 there.
- The default branch is read from the repo (`git symbolic-ref refs/remotes/origin/HEAD`, else `init.defaultBranch`, else `main`). `.ai/protected-branches` can add more per project.
- `promote-skill` and `upgrade-review` ask `ai-info --path` for the setup folder.
- A test reads each tracked file and fails on a line with a deny-list name, outside the config file. It prints the file and line.

**Rules kept:** The repo rule "This repo is generic" gets its check here. The `merge-approval` and `worktree-first` gates keep their meaning; they now read the protected branch list instead of a fixed `main` or `master`. The language list for the merge OK words (`hooklib`) moves into `AI_PROMPT_LANGS` packs; the words stay the same.

**Edge cases:**
1. Verify evidence already in git holds home paths (`state.json`, `01-cli.txt`). The ticket rewrites them as `~` and keeps stream files out of git (D10). History is not rewritten.
2. The public repo history keeps the old names. Rewriting history needs the owner and a force push, which this ticket does not do. The PR says so.
3. A fixture that needs a realistic name (a protected database name in the `no-destroy` cases): it uses a neutral name such as `appdb`, and the test checks the gate logic, not the name.
4. Windows paths: the setup does not support Windows. The config reader rejects a backslash path with a clear message instead of a wrong result.
5. A machine with no `config.env`: the defaults file gives each key. `ai-doctor` prints which keys come from defaults.
6. A repo with no remote, so no `origin/HEAD`: the fallback order gives `init.defaultBranch`, then `main`. A test covers a repo whose default branch is `trunk`.
7. The deny list must not be in a tracked file, or the test would find itself. It lives only in the owner's `config.env`; the repo test reads it from there and skips with a line when it is missing.
8. The ticket docs and research notes already use placeholders (`<project-a>`). The test allows placeholders in angle brackets.

**Owner steps:** None.

**Blocked by:** 17

**Status:** ready-for-agent

**Size:** M

- [ ] `ai/config.defaults.env` exists, and each key has a comment line.
- [ ] `grep -rn` for each value of the owner's deny list gives 0 hits outside the config file (test output in the PR).
- [ ] The hook files hold the rendered `AI_PYTHON` value, not a fixed path.
- [ ] `ai-adopt` on a fixture with default branch `trunk` protects `trunk`.
- [ ] `promote-skill` and `upgrade-review` name no fixed folder.
- [ ] `ai-doctor` passes on a temp HOME after only `install.sh` and no `config.env`.

**Verify:**
- Unit: `ai/tests/test_commands.py` gets `t_no_local_names` and `t_config_defaults`; `ai/tests/test_tier1.py` gets `t_adopt_trunk_branch`.
- Drive: `$H launch` a fixture with a `trunk` branch, then `$H drive cli ai-adopt` and `$H drive hook --agent claude PreToolUse` for an edit on `trunk`; a Codex payload drive of the same edit.
- Behaviour scenario: `gate-worktree-first` and `gate-merge-approval` of ticket 02.

**Rollback:** Revert. The old value files stay readable as a fallback during this ticket, so a revert loses no owner value.
