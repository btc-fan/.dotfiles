# ai-precommit

`ai-precommit` is the git pre-commit hook that ai-adopt installs. It lints and format-checks the staged files with the linters the repo has.

## Sub-features

- `precommit-python`: ruff check and ruff format --check on staged `.py` files.
- `precommit-skip`: a linter that is not installed is skipped with a line, not a failure.

## How to get to it (user POV)

- Any `git commit` in an adopted repo.

## Driving it with verify

Preconditions: `python-with-tests`, `doctor: PASS`.

- **Stage bad code.** Write `app/bad.py` with `import os,sys` and `def f( a ):` in the fixture, then `git -C <fixture> add app/bad.py`.
- **Run the hook.** `$H drive cli --fixture python-with-tests ai-precommit`. On this Mac (no ruff on PATH, no `.venv/bin/ruff`): `ai-precommit: not installed here, skipped: ruff check, ruff format`, `rc: 0`.

## Gotchas

- The result depends on the linters of the machine. On a machine with ruff the same drive must end with a non-zero `rc` and the ruff findings.

## Proof paths

- success: a clean staged file, `rc: 0`.
- cancel: n/a.
- error: bad staged code with ruff installed: non-zero `rc`. Unreachable on this Mac (see below).
- empty: nothing staged: `rc: 0`, no linter runs.
- persistence: n/a.
- Unreachable: the ruff failure. Blocked by: ruff is not installed on this Mac. Route tried: the drive above.
