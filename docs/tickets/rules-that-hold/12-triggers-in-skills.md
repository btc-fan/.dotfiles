# 12: A workflow starts from its skill, not from a prompt regex

**What to build:** The 6 prompt rows `feature-grill`, `tdd`, `diagnosing-bugs`, `ui`, `seo` and `blog` leave the router. Each workflow starts because its skill description carries the trigger words. A new small skill `feature-kickoff` gives the feature flow a skill that the model can call. Each of these skills also gets 1 index line in the always-loaded file (ticket 14).

**Why:** E1 gives these 6 rows the verdict MOVE-TO-SKILL-DESCRIPTION. `feature-grill` is the best reminder (20 fires, 50% followed), but its regex has about 1,500 characters, and its target `grill-with-docs` is typed-only (`typed_only` in `ai/routing.yaml`). `ui` fired 11 times, and 82% were not followed. As stop rules, `diagnosing-bugs` and `tdd` blocked falsely in 7 of 7 cases. The Vercel test (spec, section 3) found that the agent did not use a skill by itself in 56% of cases. So an index line is also needed.

**Solution:**
- Remove the 6 rows, their case files, and their placeholders (`{feature_flow}` and the others).
- `ai/skills/feature-kickoff/SKILL.md`, model-invocable. Its description holds the trigger: add, build or implement a feature, endpoint or page, with Romanian and Russian words.
- Its body is the short flow. First a worktree, then the grill (read the `grill-with-docs` SKILL.md and follow it). Then `to-spec` and `to-tickets` for 3 or more files, `/implement` per ticket, and `ship`. A trivial change skips the grill.
- Check each other skill description for its trigger words: `tdd`, `diagnosing-bugs` (Matt skills), `ui-ux-pro-max`, the `claude-seo` and `claude-blog` skills. The PR lists each description and its words.
- A vendored description is never edited. A missing word goes into the index line of ticket 14.

**Rules kept:**
- `feature-grill`: the `feature-kickoff` skill and 1 index line. `tdd`, `diagnosing-bugs`: their skill descriptions and 1 index line each.
- `ui`: the `ui-ux-pro-max` description and the Map line "Design". `seo`, `blog`: the plugin skill descriptions, on in a project by `.ai/enabled`.
- The rule texts in `ai/rules/feature-grill.md`, `tdd-stop.md` and `diagnosing-bugs-stop.md` are updated to name the new home. The stale "stop" names (E2, section 6) are fixed.

**Edge cases:**
1. The skill listing budget is 1% of the context window (file C, section 9). On overflow, the least-used descriptions lose their text. The new description stays under 300 characters. Ticket 16 frees budget (bundled skills name-only).
2. A name clash with another plugin (file I lists 76 OMC skills): no OMC, ponytail or Matt skill is named `feature-kickoff` today. A test fails when an installed skill has the same name.
3. Codex finds skills in `.agents/skills` and the plugin skill folders. The installer links `feature-kickoff` there too. The PR shows a Codex session that lists it.
4. Romanian and Russian trigger words: the old regexes held them. The new description holds a short list, and the ticket 02 eval cases in RO and RU (`*-ro.json`, `*-ru.json`) must still pass for `diagnosing-bugs`.
5. `seo` and `blog` plugins are off in most projects. Then their descriptions are absent. `ai-info` lists them as off (ticket 11).
6. The winner gate: `grill-with-docs` stays the winner for "New feature or kickoff interview". `feature-kickoff` calls it, so the gate must allow that read.
7. A user types a long feature request that is pasted session output: no regex runs any more, so the false fires of R-004 cannot happen.
8. Difference: `ui`, `seo` and `blog` are also the `ai-adopt --tools` catalog, so each row stays with `trigger: {}` and never fires.
9. Difference: the row `browser` (kept by ticket 11) still has a prompt trigger, so box 1 is not met; the R-004 cases moved to `browser.json`.

**Owner steps:** None after D1.

**Blocked by:** 11

**Status:** needs-owner (D1: move 6 rows into skill descriptions)

**Size:** M

- [ ] `ai/routing.yaml` has no `trigger: {prompt: ...}` key.
- [x] `ai/skills/feature-kickoff/SKILL.md` exists, is model-invocable, and passes the skill validator.
- [x] The eval cases `ai/evals/cases/feature-kickoff.json`, `-ro.json`, `-ru.json` and `-not.json` exist.
- [ ] In 3 runs, a Claude session with "add a page that lists the users" calls `feature-kickoff` in at least 2.
- [ ] The PR lists the trigger words of each of the 6 skill descriptions.

**Verify:**
- Unit: `ai/tests/test_skills.py` validates the new skill; `ai/tests/test_eval.py` checks the new case names; remove the 6 router case files.
- Drive: `$H drive session claude --fixture python-with-tests 'add a page that lists the users'` and the same on codex; the evidence shows the Skill call or the SKILL.md read.
- Behaviour scenario: `ai-eval behaviour` for `feature-kickoff`, `tdd` and `diagnosing-bugs` (EN, RO, RU); the 12 gate scenarios still pass.

**Rollback:** Revert. The 6 rows and their case files come back; delete `feature-kickoff`.
