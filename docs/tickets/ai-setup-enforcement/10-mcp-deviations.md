# 10: MCP deviations between SPEC.md and the install

**What to build:** Serena tools are visible from the first turn in Claude (alwaysLoad: true in the ai-serena plugin, as SPEC.md requires; ai-doctor checks it); SPEC.md says what is true now (GitHub MCP and Grounded Docs dropped on 2026-11-12); graphify 0.9.111 is audited and accepted; the OMC LSP and ast-grep server stays a fallback behind Serena.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A fresh Claude session lists Serena tools without a tool search
- [ ] ai-doctor fails when alwaysLoad is missing
- [ ] SPEC.md has no row that says GitHub MCP or Grounded Docs is installed
- [ ] audit-accepted has a line for graphify 0.9.111
