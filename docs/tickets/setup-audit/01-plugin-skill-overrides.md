# 01: The OMC skills we switch off are really off

**What to build:** a skill of oh-my-claudecode that the setup switches off does not show in the skill list of a session. Today the setup writes `skillOverrides` entries for 6 OMC skills (`pr`, `research`, `tdd` per project; `create-verification-skill`, `maintain-verification-skill`, `release` global). In a real session on 2026-11-18 all 6 were still in the skill list. The Claude Code skills documentation says that `skillOverrides` does not apply to plugin skills. Only the winner gate stops them, and only at the Skill call.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A test starts a headless session and reads its skill list. Red today: the 6 names are in the list.
- [ ] The setup uses a method that works for plugin skills, or it removes the dead `skillOverrides` entries and the docs say that the winner gate is the only guard.
- [ ] `ai-doctor` reports a switched-off skill that still shows in the list.
- [ ] The GUIDE and the skills guide state the real behaviour.
