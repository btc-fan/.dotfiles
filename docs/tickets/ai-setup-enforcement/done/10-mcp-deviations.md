# 10: MCP deviations between SPEC.md and the install

**What to build:** Serena tools are visible from the first turn in Claude (alwaysLoad: true in the ai-serena plugin, as SPEC.md requires; ai-doctor checks it); SPEC.md says what is true now (GitHub MCP and Grounded Docs dropped on 2026-11-12); graphify 0.9.111 is audited and accepted; the OMC LSP and ast-grep server stays a fallback behind Serena.

**Blocked by:** 01

**Status:** done (boxes 1 and 4 moved to ticket 12: they need a real session and the server)

- [ ] A fresh Claude session lists Serena tools without a tool search (config set: `alwaysLoad: true`). Moved to ticket 12: it needs a real session after install.
- [x] ai-doctor fails when alwaysLoad is missing
- [x] SPEC.md has no row that says GitHub MCP or Grounded Docs is installed (the drops are in section 16 "Not adopted")
- [ ] audit-accepted has a line for graphify 0.9.111. Moved to ticket 12: `agent-audit pypi graphifyy 0.9.111` needs the server profile (on this Mac: SKIPPED, exit 3 "guarddog not installed").
