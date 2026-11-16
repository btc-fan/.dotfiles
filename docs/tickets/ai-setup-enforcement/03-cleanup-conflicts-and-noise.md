# 03: Cleanup of conflicts and noise

**What to build:** the global CLAUDE.md has only the root rules import, the machine line and a 3-line OMC note; RTK does not rewrite in auto mode; the auto mode environment of one repo moves out of the global settings; the router L2 question fires only on owner prompts.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Installer writes the short CLAUDE.md; ai-doctor fails when it grows back
- [ ] Auto mode session: no "no verdict" denial from the RTK rewrite
- [ ] A task notification prompt fires no L2 question (router case)
- [ ] Install level green on all fixtures
- [ ] A task notification never counts as an owner prompt: it does not set or clear the merge-approval OK (found 2026-11-16: the router calls remember_merge_ok before any rule check, so a notification that says "merge" could set the OK, and any notification clears it)
- [ ] The OMC block in the global CLAUDE.md becomes the 3-line note; an OMC update that writes the long block back is reported by ai-doctor
