# 08: The Map, the library list and old memory files are checked by a program

**What to build:** `ai-docs-check` fails when the Map of `AGENTS.md` names a path that does not exist. `ai-libs --check` runs in `make check`, so a stale Libraries block fails. `ai-doctor` fails while old Claude memory files exist. The reminder rows `knowledge-check` and `legacy-memory` leave the router.

**Why:** `knowledge-check` fired 6 times in 7 days, and 67% were not followed. `legacy-memory` fired 8 times, and 75% were not followed (E1, Task 2). Both rules are visible in the tree, so a program can check them (E1 verdict TURN-INTO-CHECK). `ai-libs --check` exists already ("exit 1 when the section is missing, stale, or misses a direct dependency"), but no `make check` runs it.

**Solution:**
- `ai-docs-check` reads the Map section (between the `AI:map` markers, else under `## Map`). Each code span that looks like a path must exist under the repo root.
- A "path" holds a `/` or a file extension and no space. A span with `*` or `?` is a glob, and it must match at least 1 file. Commands (`make check-fast`) and placeholders (`<app>`) are not paths.
- `ai-check-detect` adds a `LIBS_LINE` to the Makefile `ai checks` block: `ai-libs --check`. This repo's own `make check` runs it too.
- `ai-doctor` (machine mode) FAILs while a `memory` folder with files exists under the Claude projects folder. The message names each folder and the step: move the facts into that repo, then delete the files.
- `ai-doctor --project` reports only the memory folder of that project.
- Remove the rows `knowledge-check` and `legacy-memory`, their case files and their placeholders. `legacy_memory_dir` in `hooklib` stays, because `ai-doctor` calls it.

**Rules kept:** "After a commit that adds, deletes or renames modules, update the Map" moves to `ai-docs-check`. "After a dependency change, run `ai-libs --sync`" moves to `ai-libs --check` in `make check`. "Knowledge lives in the repo only" stays text in the global file until ticket 14, and its memory part moves to `ai-doctor`. Claude auto memory stays off by the setting `autoMemoryEnabled: false`.

**Edge cases:**
1. Map lines with globs (`src/**/*.py`): matched with `glob`, recursive. A glob with 0 matches fails with the line.
2. Code spans that are not paths (`make check`, `@AGENTS.md`, `v2.1`): the rule above skips them. A test lists 10 real Map lines and the expected result of each.
3. A project with no Map section: the check prints "no Map: skipped" and passes. `ai-adopt` writes a Map, so only a project that is not adopted has none.
4. A project with no dependency files: `ai-libs --check` must pass with "no dependency files". The ticket tests this first; if it exits 1 today, it fixes that.
5. Memory files of another project: the machine check lists every project folder with memory files. The owner fixes them one by one; the check stays red until then.
6. A monorepo: each nested `AGENTS.md` Map is checked against its own folder, not the repo root.
7. A path in the Map that is gitignored on purpose (`.env.example` exists, `.env` does not): the Map names files that exist in a clean clone. The message says to drop or fix the line.
8. Codex: it has no Claude memory folder, so the check is Claude-only and says so.
9. Difference: `ai-doctor` did not call `legacy_memory_dir` before this ticket. The new memory check calls it now, so it stays.
10. Difference: this repo has no Makefile. Its check is `ai/tests/run.sh`, so `ai-libs --check` runs there.
11. Difference: a bare name (`router.py`, `done/`) passes when any file or folder has that name. The Map names files relative to the folder on the line before.
12. A global git ignore that lists `AGENTS.md` hides it. The check then prints "git sees no AGENTS.md: Map check skipped".

**Owner steps:** None.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Size:** S

- [x] `ai-docs-check` fails on a fixture whose Map names `src/gone.py`, and names the line.
- [x] `ai-docs-check` passes on a Map with a glob that matches, a command span and a placeholder.
- [x] The Makefile block that `ai-adopt` writes has the `ai-libs --check` line.
- [x] `ai-doctor` fails on a temp HOME that holds a project memory file, and passes after the file is removed.
- [x] `ai/routing.yaml` has no row `knowledge-check` and no row `legacy-memory`.

**Verify:**
- Unit: `ai/tests/test_knowledge.py` gets `t_map_path_missing`, `t_map_non_paths` and `t_libs_check_in_make`; `ai/tests/test_commands.py` gets `t_doctor_legacy_memory_fail`. Remove `ai/tests/cases/knowledge-check.json` and `ai/tests/cases/legacy-memory.json`.
- Drive: `$H drive cli --fixture python-with-tests ai-docs-check` after a Map edit; `$H drive cli ai-doctor --quick` with a memory file in the temp HOME.
- Behaviour scenario: the ticket 02 gate scenarios still pass.

**Rollback:** Revert. The 2 reminder rows come back, and the new checks go.
