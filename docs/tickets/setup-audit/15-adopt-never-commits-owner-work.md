# 15: ai-adopt never commits work or files that the owner kept out of git

**What to build:** the adopt commit holds only the lines that the adopt wrote. Found in the fixture experiment of
2026-11-18:

1. Uncommitted edits in `CLAUDE.md`, `Makefile` and `.gitignore` (files that the adopt also writes) went into the
   commit "adopt base AI setup v4". The tree was clean after it, so nothing showed the loss of the WIP state.
2. `CLAUDE.md`, `AGENTS.md` and `.claude/settings.json` were untracked and hidden by the owner's global git
   ignore. The adopt commit added them.

With a remote the adopt also pushes, so both cases can publish text that the owner kept local.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Red first, case 1: a fixture with a WIP line in each of the 3 files. Today the line is in the adopt commit.
- [ ] Red first, case 2: a fixture where a global ignore hides the 3 files. Today the commit adds them.
- [ ] The adopt stops before it writes when a file it must change has uncommitted edits, and names the files.
- [ ] The adopt does not add a file that git ignores for the owner. It prints the file and what to do.
- [ ] The dry run shows both cases.
- [ ] Two lines in `docs/REGRESSIONS.md`.
