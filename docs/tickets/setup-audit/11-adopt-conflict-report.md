# 11: ai-adopt reports conflicts with an AI setup that the project already has

**What to build:** `ai-adopt --dry-run` on a project with its own AI setup prints one conflict report before it writes a file. Today the owner finds the conflicts by hand after the adopt. The radar999 adoption needed a second PR to unify the old project agents and path rules with the setup.

Conflicts seen or possible today:

- The project has its own rule text (a Done section, a `CLAUDE.md` with rules, Cursor or Copilot rule files). The global rules can say the opposite, and the agent gets both.
- The managed `.gitignore` block ignores `.claude/*`. A new project command or agent file is then ignored without a message. It needs `git add -f`.
- The project has its own hooks in `.claude/settings.json`, its own MCP servers, or its own git hooks. Some stop working (managed settings on servers), some run next to ours.
- `make check-fast` is red on old lint findings. Then the Stop hook blocks turns until the owner sets `no-stop-check`.
- The pr-rules gate has `scope: global`. It asks for our PR template in every repo, also in a team repo with its own template and in a repo that is not adopted.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The dry run lists: other rule files, project hooks, project MCP servers, own git hooks, tracked files under `.claude/` that the new ignore block would hide, and the result of `check-fast`.
- [ ] Each item has one line: what happens after the adopt, and what the owner can do.
- [ ] A fixture repo with each conflict; the report names each one.
- [ ] The owner decides on pr-rules outside the owner's repos: keep global, limit to adopted repos, or a per-repo switch.
- [ ] The GUIDE scenario "Adopt an existing mess" shows the report.
