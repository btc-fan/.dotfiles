# 01: Generator builds a full verify tool, run by the AI

**What to build:** an agent in a project with app code runs `create-verification-skill` by itself and gets a `verify-<app>` tool that covers every surface (HTTP API, web UI, CLI, workers) with the atlas proof set. The owner never types the generator.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The adapter keeps the pstack text word for word, except: the typed-only flag is removed (create and maintain), and "pick the primary one and note the rest" becomes "cover every surface".
- [x] The adapter appends one "Our additions" section: a driver per surface (HTTP helper, Playwright for a web UI with 3 or more pages, PTY or tmux for a CLI, job trigger plus stored-state read for workers; Maestro named only), the atlas proof set (success, cancel, error, empty, persistence, named unreachable paths), worktree-aware doctor, full sweep order in the map index, a journeys file, the feature file updated in the same PR, evidence in `.verify/evidence/<run>/` in the repo folder, and the log fields the hooks read (commit SHA, doctor result, direct DB writes yes or no).
- [x] The verification rule doc says the AI makes the tool; the "never without the owner asking" line is gone.
- [x] The session status line and `ai-doctor` call a missing tool an agent task, not an owner step.
- [x] A test runs the adapter on the vendor copy and checks the 2 replacements and the appended section.
