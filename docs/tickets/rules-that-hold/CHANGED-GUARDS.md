# Changed guards: test files deleted by the rules-that-hold tickets

Each row is a test file that a ticket deleted after owner decision D1. The rule stays. The new check holds it.

| deleted test file | number of cases | the rule | the new check that holds the rule | the test of the new check |
|---|---|---|---|---|
| `ai/tests/cases/knowledge-check.json` | 4 | After a commit that adds, deletes or renames modules, update the Map. After a dependency change, run `ai-libs --sync`. | `ai-docs-check` fails on a Map path that does not exist; `ai-libs --check` runs in `make check` | `ai/tests/test_knowledge.py`: `t_map_path_missing`, `t_map_non_paths`, `t_libs_check_in_make` |
| `ai/tests/cases/legacy-memory.json` | 3 | Knowledge lives in the repo only: move old Claude memory files into the repo, then delete them. | `ai-doctor` FAILs while a Claude `projects/*/memory` folder holds files | `ai/tests/test_commands.py`: `t_doctor_legacy_memory_fail` |
