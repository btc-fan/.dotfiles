# 18: nav-first never fires where Serena is on

**What to build:** the first broad code search of a session (Grep, `rg`, `grep -r`, `find`) in a repo with a graph is denied once until the agent has used real navigation: Serena `find_symbol`, `find_referencing_symbols`, `get_symbols_overview`, `find_declaration`, `find_implementations`, or `graphify query` / `graphify affected`.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Cause: `router.py` `on_post_tool` sets the `nav_used` flag for any tool name that contains "serena" and for any `graphify` command. Serena's own server instructions make every session call `initial_instructions` first, so the flag is set before any search and the deny never fires.

Reproduced 2026-11-19 with verify-ai-setup (`.verify/evidence/20261119T093247Z-nav-first-audit`, fixture with a graph):
- no navigation call, then Grep: deny (correct);
- `mcp__plugin_ai-serena_serena__initial_instructions`, then Grep: allow (the bug).
A project session showed 1 nudge, then 52 broad searches in 34 minutes.

- [ ] Red: a case in `ai/tests/cases/nav-first.json`: `initial_instructions`, then Grep, expects deny.
- [ ] Green: `nav_used` is set only by the navigation tools above (and `graphify update` does not count).
- [ ] Optional, owner decision: nudge again after every 10 broad searches with no navigation call.
