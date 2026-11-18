# 15: OMC magic keywords and context-guard stop are off

**What to build:** OMC stays installed with its skills and agents, but a normal prompt never starts an OMC mode (autopilot and others) and the context-guard stop never blocks a turn. Measured: autopilot 3 of 3 false, context-guard 7 of 7 nags the agent cannot act on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The setup turns off OMC keyword detection and the context-guard stop through OMC's own settings, on every machine, and keeps them off after an OMC update.
- [x] A prompt with the word "autopilot" in a sentence starts nothing. `/oh-my-claudecode:autopilot` typed still works.
- [ ] ai-doctor reports both as off.

**Progress (2026-11-18):** keyword detection is off through OMC's own switch `OMC_SKIP_HOOKS=keyword-detector`
(`ai/adapters/env.list`, Claude settings env on every machine); ai-doctor `check_omc_walls` reports it; test
`t_omc_keywords_off` in `ai/tests/test_m3.py`. Blocked: the context-guard Stop hook. OMC 5.8.5 has no switch for it:
`context-guard-stop.mjs` reads neither `DISABLE_OMC` nor `OMC_SKIP_HOOKS` (a run with both still blocked at 80
percent), and `OMC_CONTEXT_GUARD_THRESHOLD` accepts only 1 to 94. The owner decides: accept it, ask OMC upstream for
a switch, or remove the hook another way.
