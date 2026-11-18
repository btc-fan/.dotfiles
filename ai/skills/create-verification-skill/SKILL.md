---
name: create-verification-skill
description: "Generate a project-local verification skill that drives your app the way a user does - any language, framework, or platform. Use for /create-verification-skill, \"make a control skill for this repo\", or when a project has no scripted way to prove UI/CLI/service behavior. Also at the first feature task in a project without a verify-<app> skill. RO: \"creeaza skill-ul de verificare pentru proiect\". RU: \"создай навык проверки для проекта\"."
---

> Adapted from pstack (MIT, Copyright (c) 2026 Lauren Tan; LICENSE in this folder), github.com/cursor/plugins commit 3dbd22ff12742fb28c9700b9760baa29ed41dc13. Change here: project skills live in `.agents/skills/verify-<app>/` (Codex reads them there); `ai-adopt` adds the committed link `.claude/skills/verify-<app>` -> `../../.agents/skills/verify-<app>` for Claude. Also changed: both skills are model-invocable, step 1 covers every surface, and the last section, Our additions, is ours.

# Create a verification skill

Every serious project needs a scripted way to drive the real app and prove behavior: launch it, exercise a feature the way a user would, and capture evidence. This skill generates that as a project-local skill (`.agents/skills/verify-<app>/`) tailored to the repo. You write the generator's output for the next agent, not for a human: it will be read cold, mid-task, by an agent that has never seen the app.

## 1. Interview the repo, not the user

Answer these from the codebase and only ask the user what you cannot observe:

- **Surface:** what does a user actually touch? A web UI, a CLI/TUI, a desktop app, an API, a mobile app, a library? A repo can have several; cover every surface the repo has, each with its own driver (see Our additions).
- **Run:** how does the app start locally? Prefer the repo's own documented dev command (package scripts, Makefile, README quickstart). Note ports, env vars, seed data, auth.
- **Drive:** how can an agent interact with it programmatically? Existing harnesses first - Playwright/Cypress specs, expect scripts, PTY helpers, curl-able endpoints, a debug port. Only then pick a generic recipe: browser/CDP for web and Electron, a tmux/PTY harness for CLI/TUI, plain HTTP for services.
- **Observe:** what evidence can be captured? Screenshots, terminal transcripts, response bodies, logs, exit codes, DB state.
- **Isolate:** can two instances run side by side (ports, data dirs, profiles)? If not, say so in the generated skill: refusing to double-drive a shared instance beats corrupting the user's session.

If the checkout doesn't build or start as-is, fix that first (or report it precisely) before generating; a skill written against a broken base teaches wrong steps. When an irrelevant missing asset blocks startup (a static dir the API never serves, a sample config), the generated skill may create it, clearly marked as verification scaffolding, and remove it in cleanup.

## 2. Generate the skill

Write `.agents/skills/verify-<app>/SKILL.md` with YAML frontmatter (`name: verify-<app>` and a `description` that names the app, the surface, and when to reach for it - without frontmatter the skill never registers) and these sections, each grounded in what the interview actually found (no placeholders left):

- **Launch:** the exact command that starts the app for verification, and how to tell it's ready (a log line, a prompt). Launch must reach a usable state from an empty data dir, including any migrations and seed data. Ready means usable, not just that a process answers. A database health check can pass while its init scripts are still running. Include teardown. For a short-lived CLI or TUI there is no server to keep alive: launch means build the binary (or install deps) once, then start each drive in its own isolated PTY or tmux session.
- **Doctor:** one read-only check that answers "is this instance worth driving?" - process up, right version/build, port owned by us, auth valid. An agent runs this first whenever anything looks off.
- **Drive:** the harness recipe with real selectors/commands from this repo, not examples. Prefer stable handles (ARIA labels, data attributes, prompt strings, route paths) over coordinates and tab order.
- **Evidence:** what to capture for a proof and where it goes. State the proof standards: exercise the real user path, not internal setters or test-only endpoints; capture the action and the resulting state, not just the final screen; verify side effects (files written, rows inserted, messages sent) alongside what's visible; mocks only where a production boundary already isolates the external system. When the safe path is a dry-run or test mode, verify what it actually skips by observing (files, network, git refs) rather than trusting its name: some dry-runs still touch the network or open a browser.
- **Cleanup:** how to tear down instances the run created. Never kill by process name; kill what you started. Cleanup removes instances and scratch state, never the evidence: proof artifacts survive the teardown, in a location the skill names.
- **Helpers:** any script the skill ships is executable and its invocation is shown in the skill body. A helper the reader has to reverse-engineer is not a helper.

## 3. Seed the feature map

Create `.agents/skills/verify-<app>/features/README.md` plus one file per user-facing feature you can identify (aim for the top 3-5 to start, from routes, commands, menus, or docs). Follow the shape in [`references/feature-map-example/`](references/feature-map-example/), with a README index and one file per feature. Each file answers, from the user's point of view: what the feature is, how to reach it, how to drive it with the harness, and what observable end state proves it works. The four H2s are `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, and `Gotchas`. If the seed data lacks a precondition that a journey needs, the journey reports a failure and the reason goes in that feature's `Gotchas`. Never weaken the journey to make it pass. The map is the repo's maintained verification source; a proof that drives one convenient entry point is incomplete when the map lists others.

## 4. Prove the generated skill before handing it over

Run its own instructions end to end once: launch, doctor, drive ONE mapped feature (one is enough; the map exists so later runs can cover the rest), capture evidence, clean up. After cleanup, confirm the evidence still exists at the named location - a cleanup that eats the proof fails this step. Fix what fails, and run the generated cleanup after every failed iteration too, so broken attempts don't strand processes and ports. A generated skill that was never executed is a draft, not a deliverable. If you proved it in a stand-in for the real target (a container in place of a fresh VM, a local stack in place of a remote one), list every setup step the stand-in did that the target will not. Those steps stay unverified until a run on the real target covers them.

## 5. Offer the maintenance loop

Point the user at `/maintain-verification-skill` for keeping the map honest as the app changes. Suggest a cadence only if they ask.

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

- Each run writes to its own folder `.verify/evidence/<run>/` in the root of the checkout that runs it (in a linked worktree: the worktree root). `<run>` is the UTC start time and a short label, for example `20261118T143005Z-checkout`.
- Add `.verify/` to the repo `.gitignore`. Cleanup never deletes `.verify/evidence/`.
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
