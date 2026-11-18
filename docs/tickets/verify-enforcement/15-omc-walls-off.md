# 15: OMC magic keywords and context-guard stop are off

**What to build:** OMC stays installed with its skills and agents, but a normal prompt never starts an OMC mode (autopilot and others) and the context-guard stop never blocks a turn. Measured: autopilot 3 of 3 false, context-guard 7 of 7 nags the agent cannot act on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The setup turns off OMC keyword detection and the context-guard stop through OMC's own settings, on every machine, and keeps them off after an OMC update.
- [ ] A prompt with the word "autopilot" in a sentence starts nothing. `/oh-my-claudecode:autopilot` typed still works.
- [ ] ai-doctor reports both as off.
