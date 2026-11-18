# 03: Review the nudges that fire on prompt words

**What to build:** the same review that the walls got on 2026-11-18, now for the nudges. A rule that fires on words in the owner's prompt is removed, or it gets a trigger on an action (a tool call, a file path, a git state). The rules that fire on actions have 0 misses in the logs. The rules that fire on prompt words are ignored most of the time.

Measured on this Mac, 7 days up to 2026-11-18 (fires, then misses):

| Rule | Fires | Misses |
|---|---|---|
| docs-lookup | 107 | 86 |
| tracker-flow | 42 | 33 |
| no-ai-base | 27 | 21 |
| feature-grill | 18 | 9 |
| ui | 11 | 9 |
| browser-not-enabled | 9 | 7 |
| blog-not-enabled | 6 | 5 |
| seo-not-enabled | 4 | 4 |

False fires seen in one session: `feature-grill` and the SEO tie-break fired on a prompt that asked for an audit and held GitHub links.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The numbers above are taken again from the 3 machines (real sessions only, no test sessions).
- [ ] Each prompt-word rule gets one decision from the owner: remove, change to an action trigger, or keep with a reason.
- [ ] A rule that stays has a router case for each false fire found in the logs.
- [ ] A link in a prompt does not select the SEO tie-break.
- [ ] `ai-doctor` shows the miss rate per rule for 7 days. A nudge with more than 2 misses in 3 fires is listed for review.
