# 17: Remove statements that are not true and settings that nothing reads

**What to build:** each sentence that an agent reads about the setup is true, and each setting in the routing
file changes something. An agent acts on these texts.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The Makefile block and the rules say "the agent Stop hook runs check-fast". On dev-mac the Stop check is
  off. The text states the real behaviour per profile, until the map ticket "What checks its own work means"
  decides the behaviour.
- [ ] The comment in the Stop check that says oh-my-claudecode never blocks when `stop_hook_active` is set is
  corrected: 2 of its Stop hooks do not read that field.
- [ ] `routing.yaml`: the keys that the router does not read are removed or wired: `prefilter`, `timeout_s`,
  `reinject_after_compaction`, `L3_regex`, `L4_gates`, `L7_miss_log`.
- [ ] The cost table in the GUIDE (35 OMC skills, 6k tokens) is replaced by current numbers (84 skills; skill
  list 29,971 characters for 135 skills).
- [ ] The tier is always "long" in the code. The branches for the other tiers and the `--tier` flag go, unless
  the map ticket on the project layer brings the tier back.
