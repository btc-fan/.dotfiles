# ai-check-detect

`ai-check-detect` reads a repo's files and prints its stack and the `check-fast` and `check` commands that ai-adopt writes into the Makefile.

## Sub-features

- `detect-python`: pyproject plus a tests folder gives pytest.
- `detect-node`: package.json scripts give `npm run test`.
- `detect-docs`: no code stack gives the Markdown checks.

## How to get to it (user POV)

- ai-adopt runs it. The owner runs `ai-check-detect --dir <repo>` to see what a check will run.

## Driving it with verify

Preconditions: a run with `python-with-tests`, `web-app`, `docs-only`, `doctor: PASS`.

- **Python.** `$H drive cli --fixture python-with-tests ai-check-detect --no-probe`. Expect `stack: python (pip, pytest)`, `check-fast: python3 -m pytest -x -q`.
- **Node.** `$H drive cli --fixture web-app ai-check-detect --no-probe`. Expect `stack: node (npm)`, `check-fast: npm run test`.
- **Docs.** `$H drive cli --fixture docs-only ai-check-detect --no-probe`. Expect `stack: markdown` and the `ai-docs-check --md` line.
- **Probe.** Drop `--no-probe` on `python-with-tests`: the tool runs `python3 -m pytest --version` and leaves pytest out when it fails.

## Gotchas

- `--no-probe` shows what the files say. Without it, the result depends on the tools of this machine.
- A repo with tests but no pyproject.toml is ticket 16 (not detected yet).

## Proof paths

- success: the 3 stacks above.
- cancel: n/a (read only, no prompt).
- error: `$H drive cli ai-check-detect --dir /nonexistent`. Expect one line `ai-check-detect: not a folder: /nonexistent` and `rc: 2` (ticket 19; before it, a Python traceback with `rc: 1`).
- empty: `empty` kind: the Markdown checks, as `docs-only`.
- persistence: n/a (read only).
- Unreachable: none.
