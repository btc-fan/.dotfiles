# verify-ai-setup run: self-check-session

Feature: the end-of-turn self-check (ticket rules-that-hold 10). Fixture: `python-with-tests`, adopted with `ai-adopt --yes` from this branch.

| Step | Result | File |
|---|---|---|
| Doctor (with agents) | PASS | `run.log` |
| `ai-adopt --yes` on the fixture | rc 0, branch `ai-adopt`, `.ai/enabled` written | `01-cli.txt` |
| Real Claude session: change `add` to return `a - b`, then end the turn | The Stop hook blocked the stop. The agent read the Makefile, ran the checks, put `add` back and ran `check-fast` again. End state: `add` returns `a + b`, `make check-fast` rc 0 | `02-session.txt` |

Notes:

- The block text in this session was the recipe guard: "the check-fast recipe in Makefile changed in this session". The run added the `check-fast` target by hand before the session, with no commit.
- The block for a failed test is proven by the hook payload drives of ticket 10 (`FAILED tests/test_calc.py::test_add`).
- Finding: `ai-adopt` wrote no `check-fast` target, because the project's own Makefile has `check`. In such a project the self-check has nothing to run. Ticket 20 takes this.
- The stream files and the session-state folder are not in git, because this repo is public.
- Cleanup: `real files changed: none`.
