# 21: verify-ai-setup fixes found by the wave 1 validator

**What to build:** the repo's own verify tool drives every case it claims, and its checks do not give false alarms.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The default headless session can run `gh` against a fake gh (it ended with "This command requires approval"); router-gates.md no longer blames the fake gh.
- [ ] The "remote heads changed" check compares only the remotes of the session being judged, so parallel sessions do not give a false alarm.
- [ ] Tickets 11 and 13 have a real-session drive in the feature map (today hook payload only).
- [ ] The validator wrappers in the wave 1 evidence folder (x-validator/) are folded into the helper where they fix a real gap.
