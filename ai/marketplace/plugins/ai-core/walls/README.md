# ai-core walls

The walls check git and gh at exec time and by state, not by command text. Nesting cannot hide a call from them.

| Part | What it does |
|---|---|
| `bin/git`, `bin/gh` | Launchers. They run `shim.py` with the real argv. |
| `shim.py` | The wrapper. Without `AI_AGENT=1`, it runs the real tool at once. In agent mode, it refuses hook skips and shell aliases. Then it sends `git commit`, `push`, `merge` and gh writes to the PreToolUse gates. |
| `hooks/reference-transaction` | The git hook. In agent mode, it stops a move or a deletion of a protected branch. |
| `ai-wall install [--dir <repo>]` | Writes the hook into the hooks folder of the repo. It keeps an earlier hook and runs it after ours. |
| `ai-wall rescue <slug>` | Moves uncommitted work from a protected branch to a new worktree `../<repo>-<slug>`. |

The router writes one block to `CLAUDE_ENV_FILE` at session start. The block sets `AI_AGENT=1` and `AI_SESSION`, and puts `bin` first on `PATH`. Switches: the profile key `PROFILE_WALLS=1`, and the owner value `AI_WALLS=0` in `~/.config/ai/config.env`.

The protected branches are `main`, `master` and each name in `git config --get-all ai.protected`. A move passes in 3 cases: the ref is new, the new commit is on the upstream branch, or the session has the owner's merge OK.

## Open by design

A server-side branch rule covers these forms:

- The absolute path of the real git with `-c core.hooksPath=/dev/null`.
- An inline `AI_AGENT=0`.
- A deletion of the hook file.
- A remote-tracking ref that is moved first.
- `git rebase --exec`, because git puts its own folder first on `PATH`.

Tests: `python3 ai/tests/test_walls.py`.
