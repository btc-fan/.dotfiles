# 20: nav-first denies a search for a code symbol of the graph

**What to build:** a repo has a graph. A broad search (`rg`, `grep -r`, the Grep tool) names a code symbol of `graphify-out/graph.json`. The router denies it once for that symbol. The deny names the symbol, its file and line, and the navigation order (graphify, then Serena). The same search passes on a retry. Text searches pass.

**Blocked by:** None (can start immediately)

**Status:** done (2026-11-19)

Why: `nav-first` fires once per session. One project session showed 1 nudge, then 45 broad searches in 34 minutes. 13 of them named 21 code symbols of the graph, with 7 Serena calls and 0 graphify calls. A replay of that session against this change gives 13 denies (one per search with a new symbol).

- [x] Red: a case in `ai/tests/cases/nav-first.json`: Serena used, one search passed, then `rg 'send_mail|MailQueue' src` expects deny with both symbols and their file and line.
- [x] The same search passes the second time. The first search of a session is denied once only, also when it names a symbol.
- [x] No deny for: a phrase, a one-word lower-case name, a name in a path, a document node, a search behind a pipe, a repo with `no-graph`.
- [x] The owner skip (`sudo ai-gate-skip nav-first`) covers this deny too (same code path as the first-search deny).
