# 07: Graph-first gate and a quiet docs-lookup

**What to build:** in a code repo with a graph, the first broad search of a session is denied once with "run graphify query first"; later searches pass. docs-lookup fires only for a library from the Libraries block or before a dependency-file edit.

**Blocked by:** 01

**Status:** done

- [x] Router cases: first search denied, second passes, no graph passes, no-graph flag passes
- [x] docs-lookup does not fire on a prompt that only says "docs"

Codex: the graph-first deny works on shell searches. docs-lookup before a dependency edit is Claude only: Codex
edits through apply_patch, which the Codex hooks do not route to the router.
