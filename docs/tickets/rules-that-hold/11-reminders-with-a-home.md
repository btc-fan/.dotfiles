# 11: The 14 reminder rules with a home in another place leave the router

**What to build:** The router stops sending the 14 reminders that E1 marks DELETE, and the 5 tie-break rows. Before each row goes, its home exists and is proven. Where a home is missing, this ticket adds it. The owner loses no rule: each one lives in the place that the README rule map names.

**Why:** 27 of 39 rules only add text. 321 fires in 7 days, 241 not followed (75%). The worst one, `docs-lookup`, fired 107 times, and 80% were not followed. The context7 server sends the same instruction in each session (spec, section 2). No other studied setup injects reminders from a regex on the prompt (spec, section 3). The older ticket `docs/tickets/setup-audit/03-prompt-word-nudges.md` reviewed the same rows; this ticket applies the verdict.

**Solution:**
- Commit 1 removes the 14 DELETE rows: `no-ai-base`, `merge-review`, `upgrade-review`, `nav-first`, `ledger-nudge`, `docs-lookup`, `verify-before-done`, `seo-not-enabled`, `blog-not-enabled`, `browser-not-enabled`, `omc`, `browser`, `tracker-flow`, `domain-docs`.
- Commit 2 removes the 5 `tiebreaks` rows. The `winners` table stays as data for the winner gate.
- Each row goes with its case file in `ai/tests/cases/`, its line in the L0 table and its golden fixture text.
- Homes to add before the delete: `ai-doctor --project` prints "no AI setup here: run ai-adopt" for a repo with no `.ai/` folder. `ai-info` lists the opt-in tools that are off in this project. The `ship` skill names `/improve-codebase-architecture` and `/retro` as the step after a merge.
- `upgrade-review`: `install.sh` and `ai-sync` print one line when `ai-versions` records a new version. With `--upgrade-review` they run the skill once as a headless job.
- `nav-first` goes only when the ticket 02 numbers (on and off) show no loss. Else the row stays, and the PR says so with both numbers.

**Rules kept:**
- `docs-lookup`: the context7 server instructions, plus 1 index line (ticket 14). `tracker-flow`: `docs/agents/issue-tracker.md`, plus 1 index line.
- `no-ai-base`: the `setup-rollout` skill and the new `ai-doctor` line. `upgrade-review`: the install and sync step. `merge-review`: the `ship` skill.
- `verify-before-done`: the verify walls. `domain-docs`: the `domain-modeling` skill description. `browser`: the Playwright MCP tool descriptions.
- `*-not-enabled`: `ai-info` and the tool list in the rules file. `omc`: the managed `.gitignore` block. `ledger-nudge`: `ai-ledger --check` in `make check`.
- `nav-first`: 1 line in the rules file, and the deny only if the numbers keep it.

**Edge cases:**
1. The UserPromptSubmit hook must still store the owner's merge OK. A test sends "merge" after the change and expects the `merge-approval` gate to allow `gh pr merge`.
2. The 6 prompt rows of ticket 12 stay in this ticket. So the prompt-matching code stays; ticket 17 removes it.
3. Rendered files: `ai-render` writes `routing.json` and `L0.md` again; the golden fixtures of ticket 03 change in the same commit.
4. The miss log: old rows in `misses.jsonl` keep their rule ids. `ai-doctor --numbers` shows them in the 7-day history and 0 new fires after the change.
5. Docs that name the rows: `README.md`, `docs/GUIDE.md` and the `ai/rules/*.md` files. A grep for each removed id is in the PR, with 0 hits outside history files.
6. Codex reads the same `routing.json`. Routing is data, so Codex needs no new hook trust. The Hermes copy reads it through `ROUTING_OVERRIDE`; it changes with the render.
7. A second machine that is one commit behind keeps the old rows until its `ai-sync` runs. Nothing breaks: the router and the render come from one checkout.
8. A session that is open during the change: the router reads `routing.json` on each event, so the reminders stop at once. The L0 text already in that context stays until a compaction.
9. `upgrade-review` as a headless job needs a login and can hit a usage limit. The step then prints the command for the owner and exits 0.
10. `nav-first` stays: the same task cost 78,169 tokens with it on and 97,965 with it off (docs/reports/scenarios-baseline-2026-11-20.md).
11. `omc` and `browser` stay: their opt-in rows are also the catalog of `ai-adopt --tools`, and no other catalog exists yet.
12. Only the tie-break `library API docs` goes. The other 4 serve the kept rows `seo`, `blog` and `feature-grill`; ticket 12 removes them.
13. `ai-doctor` checks `.ai/base-version`, not the `.ai/` folder: ai-adopt writes that file, and the removed rule used it.
14. The merge OK case already exists: `ai/tests/cases/merge-approval.json` "owner said merge it: allowed".
15. `merge_review_note` also named `ai-evidence-prune`; the `ship` skill now names it after the merge.

**Owner steps:** None after D1.

**Blocked by:** 01, 02, 03

**Status:** needs-owner (D1: delete the 14 reminder rows and their test files)

**Size:** M

- [ ] `ai/routing.yaml` has none of the 14 ids and no `tiebreaks` key.
- [x] `ai-doctor --project` in a repo with no `.ai/` prints the `ai-adopt` line.
- [x] `ai-info` in an adopted project lists the opt-in tools that are off.
- [x] The `ship` skill names the after-merge step.
- [x] A prompt "merge" still opens the merge gate (test case).
- [x] `nav-first` is gone with both numbers in the PR, or it stays with both numbers in the PR.
- [ ] `ai-doctor --numbers` shows 0 fires of the removed ids in a new session.

**Verify:**
- Unit: `bash ai/tests/run.sh`; `ai/tests/cases/merge-approval.json` gets a case for the stored OK; remove the 14 case files and `_tiebreaks.json`.
- Drive: `$H drive hook --agent claude UserPromptSubmit '<prompt with library words>'` shows no reminder; `$H drive cli ai-doctor --project` in an empty fixture.
- Behaviour scenario: all 12 gate scenarios and the navigation scenario of ticket 02.

**Rollback:** Revert commit 2, then commit 1. The rows, the cases and the text come back.
