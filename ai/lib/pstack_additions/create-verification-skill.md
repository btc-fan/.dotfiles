## Our additions

These rules come from our AI setup, not from pstack. Where they differ from the steps above, these rules win.

### When you build the tool

- You build the tool. The owner does not type this skill. Run it at the first feature task in a project that has no `verify-<app>` skill.
- That feature task waits until the tool passed one real run (step 4). A tool that never ran is a draft, and a draft does not count.

### A driver per surface

Cover every surface the repo has. Give each surface its own driver in **Drive**:

- **HTTP API and form posts:** an HTTP helper script. It sends the request and saves the status and the response body.
- **Web UI with 3 or more pages:** a Playwright mode. Playwright needs the browser tool in the project (`ai-adopt --tools browser`). When the browser tool is off, write that in the skill and give the owner that command. Never install a browser tool yourself. Save a screenshot and the ARIA snapshot per step.
- **Web UI with fewer than 3 pages:** the HTTP helper reads the rendered page. Use Playwright when the browser tool is on.
- **CLI or TUI:** one PTY or tmux session per drive. Save the transcript and the exit code.
- **Workers and scheduled jobs:** a job trigger (the real queue, command or endpoint that starts the job), then a read of the stored state that the job wrote (rows, files, messages).
- **Mobile app:** name Maestro as the driver in the skill. Do not install it.

### The atlas proof set

Each feature file gets a fifth H2, `Proof paths`. It lists these paths, each with its drive steps and the end state that proves it:

- **success:** the normal user path completes.
- **cancel:** the user backs out; nothing is stored.
- **error:** bad input or a failed dependency; the app shows or returns the error.
- **empty:** no data yet; the empty state shows.
- **persistence:** the result survives a reload or a restart.

Write `n/a` and the reason when a path does not exist for the feature. A path that you cannot drive goes under `Unreachable`, with what blocks it (auth, entitlement, OS, external state) and the route you tried. Every path is driven, `n/a`, or unreachable with its blocker.

### Doctor knows its checkout

Each checkout and each linked worktree runs its own instance, with its own port and its own data folder (for example `<checkout>/.verify/data/`). Derive the port from the checkout path, or record it in the data folder. The doctor prints the checkout root (`git rev-parse --show-toplevel`) and FAILs when the instance on the port was started from another checkout.

### Map index and journeys

- `features/README.md` lists every feature file in a full sweep order: the order of a broad regression run. Features that make data come before the features that use it.
- `multi-surface-journeys.md` in the skill folder lists the flows that cross surfaces (for example: a form post in the UI, then a worker job, then the result in the API). Each journey has drive steps and the end state, like a feature file.
- A PR that adds or changes a user-facing feature adds or updates its feature file in the same PR.

### Evidence and the run log

- Each run writes to its own folder `.verify/evidence/<run>/` in the root of the checkout that runs it (in a linked worktree: the worktree root). `<run>` is `<branch>_<feature>_<DD-MM-YYYY>_<HH-MM-SS>`: the branch (a `/` becomes `-`), the feature label (left out when it is the same as the branch), and the UTC start time in EU date order. Example: `fix-cart-total_checkout_18-11-2026_14-30-05`.
- The repo `.gitignore` ignores `.verify/` except `.verify/evidence/` (the managed block of `ai-adopt`). Cleanup never deletes `.verify/evidence/`.
- Commit each run folder with the change it proves, on the feature branch. The owner reads the proof on GitHub from any machine. A cleanup PR removes runs older than 7 days from main (`ai-evidence-prune`).
- Each run writes `summary.md` in its run folder: the feature, each step with PASS or FAIL, and the names of the evidence files. A reader opens this file first.
- Never write secrets, tokens, cookies, passwords or DB dumps into the run folder. Mask them before you save a response body or a log. App data stays in `.verify/data/`, which is not committed.
- A relaunch after a failed doctor starts a new run folder.
- A helper script in the skill folder makes the run folder and writes `run.log` in it. The agent never writes `run.log` by hand.

`run.log` is plain text. Each line is `key: value`, with a lower-case key. The AI setup's verify hooks parse these lines (contract: `~/.config/ai/rules/verification-skill.md`). Other lines are ignored. Write each key once:

| Line | Value |
|---|---|
| `commit: <sha>` | The full 40-character SHA of `git rev-parse HEAD` in the checkout, at the start of the run. |
| `doctor: PASS` or `doctor: FAIL` | `PASS` only when every doctor check of the run passed. One failed check makes it `FAIL`. |
| `db_writes: yes` or `db_writes: no` | `yes` when any step changed the app's stored data by a way other than the app's own surfaces: an SQL client, an ORM shell, a direct edit of a data file. The migrations and seed data of Launch, before the first doctor, do not count. |
| `finished: <time>` | The UTC end time in ISO 8601, for example `2026-11-18T14:31:40Z`. The helper writes it last, after cleanup. |

Example:

```
commit: 4be8c1d0f2a7e93b5c6d1e0f9a8b7c6d5e4f3a2b
doctor: PASS
db_writes: no
finished: 2026-11-18T14:31:40Z
```

A run is proof only when all 4 lines are present, `doctor: PASS`, and `db_writes: no`. A run without `finished` did not end.
