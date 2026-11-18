# 20: OMC context-guard fires only near a full context

**What to build:** OMC 5.8.5 has no switch for its context-guard Stop hook (ticket 15). The setup sets OMC's supported knob `OMC_CONTEXT_GUARD_THRESHOLD` to 94, so the guard blocks only when the context is nearly full. Owner decision pending (asked 2026-11-18).

**Blocked by:** owner answer

**Status:** waiting-for-owner

- [ ] The env value is set on every machine by install.sh, like `OMC_SKIP_HOOKS`.
- [ ] ai-doctor shows the threshold.
