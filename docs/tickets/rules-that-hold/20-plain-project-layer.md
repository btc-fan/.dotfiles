# 20: A project gets plain files, and a monorepo works

**What to build:** `ai-adopt` gives a project plain files: the Map, the check line, `CLAUDE.md` with `@AGENTS.md`, `.ai/enabled`, the Makefile targets and a short ignore block. The generated rule blocks go where a check or a skill holds the rule. A monorepo gets small nested pointer files and check targets. An update of an adopted project removes the old blocks safely.

**Why:** E1, Task 3, reads the project layer. The `AI:done` block (9 lines) repeats rules that the verify walls and the PR gate enforce. The `AI:verify` block repeats the verify walls. The `AI:<id>` opt-in blocks repeat the skill descriptions (the `ui` block: 62 words). The `.gitignore` block has 49 lines, and 26 of them are per-skill link lines. `ai-adopt` refuses the check targets in a monorepo (R-012 is one case).

**Solution:**
- Stop writing `AI:done`, `AI:verify` and the `AI:<id>` tool blocks. Done items 2, 4 and 5 move into the `ship` skill; items 1, 3 and 6 are enforced already (E1, Task 3).
- Keep the Map, the Map "Check" line, the Map "Design" path (without its "missing: ..." clause), the Libraries block, "Lessons" and "Project rules".
- The ignore block keeps the tool folders. The per-skill link lines go to the global excludes file that `ai-start` already reads.
- A monorepo (workspace files: `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, `go.work` and the rest): each package gets a nested `AGENTS.md` of 3 to 5 lines that points to the root. The root gets `check-fast` and `check` targets that call the packages.
- An update removes each old managed block only when its text equals what `ai-adopt` wrote. Owner text inside a block is moved out first.
- Adopt works on 3 fixtures with no hand step: a plain repo, a repo with default branch `trunk`, a monorepo.

**Rules kept:** The Done list rules keep a home. Items 1 and 6 stay in the verify walls and the PR size warning. Item 3 stays in the global rule "A failing test is a blocker". Items 2, 4 and 5 go into the `ship` skill. The opt-in tool rules stay in the skill descriptions (ticket 12). The Map and Libraries rules stay in the checks of ticket 08.

**Edge cases:**
1. Owner text inside a managed block (R-006 lost such lines once): the update moves each line that `ai-adopt` did not write to "Project rules", and prints it. It never deletes owner text.
2. A project with its own Done section: `ai-adopt` already keeps it. The update removes only the `AI:verify` line under it.
3. A block with a START marker and no END marker (a test on a fixture on 2026-11-19 showed data loss: the undo removed owner text below such a block; no ledger line yet): the update stops, changes nothing in that file, and prints the line number.
4. A project whose `CLAUDE.md` is a link to `AGENTS.md` (a test on a fixture on 2026-11-19 showed it: the file got a self-import and no blocks, and the adopt committed it): `ai-adopt` detects the link and writes nothing into `CLAUDE.md`.
5. `--dry-run` writes nothing. A test hashes the tree before and after.
6. A monorepo with an owner Makefile that already has `check-fast` and `check`: the targets are kept (R-012).
7. A project that is adopted with the old layer and opened on a machine that is behind: the old router reads no block text, so a missing block breaks nothing.
8. A package folder that already has its own `AGENTS.md`: the pointer lines are added at its end inside markers, and the rest stays.

10. A project whose own Makefile has `check` and no `check-fast` (seen on 2026-11-20 in a real run): `ai-adopt` wrote no `check-fast` target, so the end-of-turn self-check had nothing to run. The ticket adds a `check-fast` target, or makes the self-check use `check` with its time limit.

**Owner steps:** None.

**Blocked by:** 14, 19

**Status:** ready-for-agent

**Size:** M

- [ ] `ai-adopt` on the 3 fixtures exits 0, and a second run changes no file.
- [ ] A new project's `AGENTS.md` has no `AI:done`, `AI:verify` or `AI:<tool>` block.
- [ ] An update of an old fixture removes the 3 block kinds and keeps a planted owner line.
- [ ] A fixture with a START marker and no END marker is left unchanged, with a message.
- [ ] The monorepo fixture gets nested pointer files, and `make check-fast` at the root runs the package checks.
- [ ] The `.gitignore` block has no per-skill link lines.

**Verify:**
- Unit: `ai/tests/test_tier1.py` gets `t_adopt_plain`, `t_adopt_trunk`, `t_adopt_monorepo`, `t_update_removes_blocks`, `t_missing_end_marker` and `t_claude_md_link`.
- Drive: `$H launch` with `empty`, `python-with-tests` and `existing-project-with-own-Done`; `$H drive cli ai-adopt --dry-run`, then `ai-adopt` in each.
- Behaviour scenario: `ai-eval install` (adopt twice per fixture) and the 12 gate scenarios of ticket 02.

**Rollback:** Revert, then run `ai-adopt` again in each project. It writes the old blocks back.
