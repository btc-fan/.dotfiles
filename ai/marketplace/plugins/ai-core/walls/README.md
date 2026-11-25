# ai-core walls

The walls check git and gh at exec time and by state, not by command text.

| Part | What it does |
|---|---|
| `bin/git`, `bin/gh` | Launchers of `shim.py`. |
| `shim.py` | The wrapper. Without `AI_AGENT=1`, it runs the real tool. In agent mode, it refuses hook skips, shell aliases and `update-ref` on `refs/remotes/`. It sends `git commit`, `push`, `merge` and gh writes to the PreToolUse gates. |
| `hooks/reference-transaction` | In agent mode, stops a move of a protected branch. |
| `ai-wall install` | Writes the hook, and chains an earlier hook. |
| `ai-wall rescue <slug>` | Moves uncommitted work to the worktree `../<repo>-<slug>`. |

A gate deny is final. An ask passes one time when the PreToolUse hook asked the owner about the same command in the last 120 s.

The session start writes `AI_AGENT`, `AI_SESSION` and `PATH` to `CLAUDE_ENV_FILE`. Switches: `PROFILE_WALLS=1`, and the owner value `AI_WALLS=0`.

Protected branches: `main`, `master` and each `ai.protected` name. A move passes when the ref is new, or with the owner's merge OK. A fast-forward to work on the upstream branch also passes.

## Open by design

A server-side branch rule covers these forms:

- The absolute path of the real git with `-c core.hooksPath=/dev/null`.
- An inline `AI_AGENT=0`.
- A deletion of the hook file.
- `git fetch` from the repo itself into a remote-tracking ref.
- `git rebase --exec`: git puts its own folder first on `PATH`.

Tests: `python3 ai/tests/test_walls.py`.
