# 09: ai-adopt for empty, docs-only and non-git folders

**What to build:** ai-adopt sets up an empty git repo and a docs-only repo fully, with a make check (Markdown placement, em dash, links); refuses a folder without git unless --init; commits on a branch, not on main; warns when there is no remote. At session start, a repo with code and no graph gets a background graph build, and the Serena and graph rules switch on.

**Blocked by:** 01

**Status:** done

- [x] Install level green on the empty, docs-only and no-git fixtures
- [x] Second run changes nothing
- [x] First code file in an empty fixture: graph exists after the next session start
- [x] Install level of ai-eval also runs ai-doctor (project checks) and an uninstall, moved here from ticket 01
