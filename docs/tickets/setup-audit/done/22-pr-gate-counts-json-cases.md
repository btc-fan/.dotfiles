# 22: The pr-rules gate counts JSON test cases as a test file

**What to build:** a fix PR in this repo can add or change a case file in `ai/tests/cases/*.json`. That PR passes
the "a fix PR has a test file" check of the pr-rules gate. Today only a Python test file counts.

**Blocked by:** None (can start immediately)

**Status:** done (2026-11-19)

Why: PR #21 (nav-first symbol deny) had its tests as JSON cases. The gate blocked the PR, and the agent added a
Python unit test only to pass the gate.

- [x] Red: a gate case with a fix PR whose diff has only `ai/tests/cases/<rule>.json` expects pass. It fails now.
- [x] Change `PR_TEST_PATH` in `ai/marketplace/plugins/ai-core/hooks/hooklib.py`. It counts `tests/cases/*.json`.
  The file `ai/hooks/hermes/hooklib.py` is a generated copy that git ignores.
- [x] A fix PR with no test file and no case file is still blocked. Fixture JSON under `tests/` is not a case file.
