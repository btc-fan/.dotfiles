# 12: Final audit and rollout

**What to build:** an independent audit against the goals G1 to G10, then re-adopt of the real projects on the Mac (server-start first, for the owner to test), 7 days of ai-doctor numbers, a retro, then the same rollout on the home server.

**Blocked by:** 02, 03, 04, 05, 06, 07, 08, 09, 10, 11

**Status:** ready-for-agent

- [ ] Audit findings are tickets
- [ ] server-start has the full setup and the owner tested it
- [ ] Numbers after 7 days are better than the baseline
- [ ] A fresh Claude session lists Serena tools without a tool search (`alwaysLoad: true`), moved here from ticket 10
- [ ] audit-accepted has a line for graphify 0.9.111: run `agent-audit pypi graphifyy 0.9.111` on the server profile, then add the line, moved here from ticket 10
- [x] ai-adopt runs make check-fast before ai-docs-check --init, so existing stray Markdown fails the first check and the Stop hook goes off (found on server-start, 2026-11-16)
- [x] ai-adopt appends no-stop-check to .ai/enabled after its commit and leaves it uncommitted (found on server-start)
- [ ] ai-doctor wording: the short CLAUDE.md and the autoMode check print WARN with a pass-like text
- [ ] SessionStart context after compact/clear is over 9500 chars (the L0 tail is cut): trim
- [ ] Public repo: docs/GUIDE.md names a host and private repos; rtk.md line 18 contradicts the installer; done/01 and done/02 have no ticked boxes
- [ ] docs-lookup eval case: the app fixture has no Libraries block, so the prompt nudge cannot fire there
- [x] ai-adopt writes the check-fast seconds and the ai-libs rows into AGENTS.md after its commit (found 2026-11-17)
- [x] An ai-adopt rerun replaced the managed Makefile block and dropped an owner flag on a command line (found 2026-11-17)
- [x] The OMC note in ~/.claude/CLAUDE.md on every OMC wiring (plugin and npm CLI): the root rules step already writes it since the last merge; a test pins both wirings (2026-11-17)
- [x] ai-doctor FAILs the bare RTK hook when the owner switch says off (found 2026-11-17)
