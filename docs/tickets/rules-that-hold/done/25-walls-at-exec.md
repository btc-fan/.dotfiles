# 25: The git rules hold at exec and by state, not by command text

**What to build:** Three parts. The session start puts a git and gh wrapper first on `PATH`. A `reference-transaction` hook guards the protected branches. A rescue command moves work off them. The wrapper reads the real argv after the shell parsed everything. The hook reads the ref updates that git is about to make.

**Why:** The PreToolUse gates read the text of a command. A red team found 125 forms that pass: a here-document, a brace group, an `if`, an alias, `-c core.hooksPath=/dev/null` and an abbreviated `--no-verify`. Claude Code runs the file named by `CLAUDE_ENV_FILE` before each Bash command, so a `PATH` entry there reaches each nested call. Git runs `reference-transaction` for each ref update, also under `--no-verify` (`docs/research/git-hooks-seam.md`).

**Solution:**
- `walls/shim.py` with the launchers `walls/bin/git` and `walls/bin/gh`. Without `AI_AGENT=1`, it runs the real tool at once.
- In agent mode, it refuses `-c`, `--config-env` and `GIT_CONFIG_*` entries for `core.hooksPath`, `alias.*` and `hook.*`. It refuses `--no-verify` and each abbreviation, and `-n` in a `commit` flag cluster.
- It resolves a config alias with the real git and refuses a shell alias. It refuses a `core.hooksPath` outside the repository.
- `git commit`, `push`, `merge` and gh writes go to `router.on_pre_tool` with one command built by `shlex.join`. A deny exits 1. An ask passes one time with a fresh pass that the PreToolUse hook recorded after it asked the owner.
- The wrapper refuses `git update-ref` on `refs/remotes/`, and `update-ref --stdin`, because the wrapper cannot read its input.
- `walls/hooks/reference-transaction` aborts a move of `main`, `master` or an `ai.protected` branch in agent mode. A new ref, a fast-forward to work on the upstream and the owner's merge OK pass. A rewind to an older commit is stopped.
- `walls/ai-wall install` writes and chains the hook. `walls/ai-wall rescue <slug>` moves uncommitted work to `../<repo>-<slug>`.
- `router.py` `on_session_start` appends one block to `CLAUDE_ENV_FILE` for Claude. Switches: `PROFILE_WALLS=1` (dev-mac) and the owner value `AI_WALLS=0`.

**Rules kept:** Each gate keeps its logic and its text check. The wrapper calls the same gates a second time with the real argv. The `no-verify` gate is not asked by the wrapper, because the argv check is its exact form.

**Edge cases:**
1. `git update-ref` and `git branch -f` give zeros as the old value. The hook reads the old value from the ref itself.
2. `git stash` rewrites the branch to the same commit. The hook lets a rewrite to the same commit pass.
3. A rewind (`reset --hard HEAD~1`) lands on an ancestor of the upstream. The hook also needs the current value to be an ancestor of the new value.
4. Inside a git hook and in `git rebase --exec`, git puts its own folder first on `PATH`. The wrapper does not run there.
5. The wrapper cannot ask the owner. The PreToolUse hook records a pass for each git or gh stage of a command it asked about. The pass is the hash of `shlex.join` of the words, valid 120 s, used one time. A command that the hook did not see gets no pass.
6. An owner `core.hooksPath` in the global or system config passes, unless it is `/dev/null`.

**Owner steps:** None. Wiring `ai-wall install` into project adoption is a later ticket.

**Blocked by:** None

**Status:** done

**Size:** M

- [x] 152 attack payloads hold: local `main`, origin `main` and the stub gh do not change.
- [x] 20 friendly payloads pass with the right outcome.
- [x] An approved ask passes one time. A nested ask, an old pass and a deny are refused.
- [x] 5 open forms are asserted and labeled "open, by design".
- [x] `ai-wall install` twice, with an earlier hook, and in a linked worktree.
- [x] `ai-wall rescue` moves staged, unstaged and untracked work, and names the local commits.
- [x] The median added time for `git status` is printed. The limit is 150 ms.

**Verify:**
- Unit: `python3 ai/tests/test_walls.py`, also in `bash ai/tests/run.sh`.

**Rollback:** Set `AI_WALLS=0` in `~/.config/ai/config.env`, or revert the commit.
