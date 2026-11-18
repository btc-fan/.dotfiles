# ai-doctor project checks

`ai-doctor --project-only <path>` checks the project layer of one repo (Map, sizes, secrets, graph, `.gitignore`) and prints one PASS, WARN or FAIL line per check.

## Sub-features

- `doctor-project`: the project checks with a summary line.

## How to get to it (user POV)

- The owner runs `ai-doctor` in a project. `ai-eval install` runs `--project-only`.

## Driving it with verify

Preconditions: an adopted fixture (see ai-adopt.md), `doctor: PASS`.

- **Adopted repo.** `$H drive cli --fixture python-with-tests ai-doctor --project-only .`. Seen on 2026-11-18: `ai-doctor: 18 pass, 3 warn, 0 fail, 0 skip`, `rc: 0`.

## Gotchas

- The machine checks (plugins, router tests) are not driven: they read the real HOME, and the driver gives a temp HOME. Use `--project-only`.

## Proof paths

- success: the adopted fixture, `0 fail`.
- cancel: n/a (read only).
- error: run it on a fixture that was not adopted. Seen on 2026-11-18: `ai-doctor: 5 pass, 6 warn, 0 fail, 0 skip`, `rc: 0`, with `WARN AGENTS.md Map section` and `WARN AGENTS.md Done section`. A missing layer is a WARN, never a FAIL.
- empty: the `empty` kind after ai-adopt.
- persistence: n/a (read only).
- Unreachable: the full machine doctor. Blocked by the temp HOME. Route tried: `--project-only`.
