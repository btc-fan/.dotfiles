# 20: OMC context-guard fires only near a full context

**What to build:** OMC 5.8.5 has no switch for its context-guard Stop hook (ticket 15). The setup sets OMC's supported knob `OMC_CONTEXT_GUARD_THRESHOLD` to 94, so the guard blocks only when the context is nearly full. Owner decision 2026-11-18: yes, threshold 94; the typed-autopilot side effect of ticket 15 is accepted.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The env value is set on every machine by install.sh, like `OMC_SKIP_HOOKS`.
- [ ] ai-doctor shows the threshold.
