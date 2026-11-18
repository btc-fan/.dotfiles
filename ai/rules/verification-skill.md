# verification skill (pstack create-verification-skill, maintain-verification-skill; project verify-<app>)

Version: newest commit of github.com/cursor/plugins (folder `pstack/`; no vX.Y.Z tags for pstack, so the default
branch HEAD, SPEC 23). Read and audited at intake: commit 3dbd22ff12742fb28c9700b9760baa29ed41dc13, pstack plugin
version 0.15.36. License MIT, Copyright (c) 2026 Lauren Tan (kept in every copy). Ideas also read (not copied):
poteto/verification-skill-example (verify-atlas, a feature map per area) and kody-hq/kody `control-kody` (one CLI:
doctor, dev, request, browse, verify <feature>, health; "CI green is not enough", local verification first).

## Vendor rules (verbatim)
The verbatim text is in `ai/rules/vendor/pstack-verification/` (both SKILL.md files, the feature-map example,
LICENSE, SOURCE.md). Deviation: U+2014 became " - " (repo rule). Key lines: "Every serious project needs a scripted
way to drive the real app and prove behavior: launch it, exercise a feature the way a user would, and capture
evidence." "A generated skill that was never executed is a draft, not a deliverable." "A feature map rots the moment
the app changes."

## When / when not
- `create-verification-skill` (model-invocable since verify-enforcement 01): the AI makes the tool. The owner never
  types the generator. The agent runs it at the first feature task in a project with app code and no
  `verify-<app>` skill. It writes `.agents/skills/verify-<app>/` (SKILL.md: Launch, Doctor, Drive, Evidence,
  Cleanup, Helpers; `features/README.md` plus one file per feature; `multi-surface-journeys.md`) and proves it with
  one real run. That feature task waits until the run passed. Then `ai-adopt` adds the committed link
  `.claude/skills/verify-<app>` -> `../../.agents/skills/verify-<app>`.
- The tool covers every surface the repo has, each with its driver: an HTTP helper for APIs and form posts;
  Playwright for a web UI with 3 or more pages (the project turns on the browser tool, `ai-adopt --tools browser`);
  PTY or tmux for a CLI; a job trigger plus a read of the stored state for workers. Maestro is named for a mobile
  app, not installed.
- Each feature file lists the atlas proof set: success, cancel, error, empty, persistence, and the unreachable
  paths with what blocks them. The doctor knows its checkout or worktree (own port, own data folder).
  `features/README.md` keeps a full sweep order. A feature change updates its feature file in the same PR.
- `maintain-verification-skill` (model-invocable): when the session status says the map is stale (25 code commits,
  or 30 days with code commits, since the feature map last changed), and at least monthly in an active project.
- `verify-<app>` (the project's own skill): before "done" on every user-visible change, in this order: (a)
  `check-fast` green; (b) `verify-<app>` on the changed feature(s): launch, doctor, drive every reachable entry
  point the feature file lists, capture evidence, clean up but keep the evidence; (c) only after (b) passes, add or
  extend e2e tests that encode the proven journey (Playwright with screenshot comparison for UI, HTTP or pytest
  level for APIs, as the stack allows); (d) the PR Verify field cites the evidence path and the e2e test.
- Not for library-only repos with no user surface (then the tests are the proof).
- The source of these rules is the section `Our additions` of our create skill
  (`ai/lib/pstack_additions/create-verification-skill.md`); the adapter appends it.

## Evidence log contract (read by the hooks of tickets 02 to 05)
- One folder per run: `.verify/evidence/<run>/` in the root of the checkout that ran it (a linked worktree: the
  worktree root). `<run>` is the UTC start time and a label, for example `20261118T143005Z-checkout`. The project
  `.gitignore` has `.verify/`. Cleanup keeps the evidence.
- The project helper writes `run.log` in the run folder: plain text, one `key: value` line per key, lower-case
  keys, other lines ignored.
  - `commit: <sha>`: the full 40-character `git rev-parse HEAD` of the checkout at the start of the run.
  - `doctor: PASS` or `doctor: FAIL`: PASS only when every doctor check of the run passed.
  - `db_writes: yes` or `db_writes: no`: yes when a step changed stored data by a way other than the app's own
    surfaces (SQL client, ORM shell, direct edit of a data file). Launch migrations and seed data before the first
    doctor do not count.
  - `finished: <time>`: the UTC end time in ISO 8601 (`2026-11-18T14:31:40Z`), written last, after cleanup.
- A valid log has all 4 lines, `doctor: PASS` and `db_writes: no`. The hooks never judge proof quality; code review
  and the ship skill do.

## Enforcement
- L1: the session-start status says "Verify skill: verify-<app> (N features)", "... stale (...). Agent task: run
  maintain-verification-skill now", or "missing. Agent task: build verify-<app> with create-verification-skill at
  the first feature task, and prove it with one real run." A copy that is still typed-only on a machine adds
  "(typed-only; agent: read <path>/SKILL.md and follow it)".
- L3: row `verify-before-done` after the first code edit of each agent: the main agent and each subagent
  (`once_per: agent`, keyed on the payload's `agent_id`; only with a verify skill).
- L3: `ai-adopt` writes the Done order into every project. A project with its own Done section gets one managed
  `AI:verify` line at the end of that section; the owner text stays byte for byte.
- L3: the `release` skill runs `maintain-verification-skill` when the project has a verify skill.
- L2: the feature flow (`feature-grill`) names the verify feature per slice and the Done order.
- L4: pr-rules on `gh pr create`, `edit` and `ready`: with a verify skill and app code in the diff, a valid
  run.log at the PR head SHA that finished after the last app-code commit.
- L7: `ai-doctor --project`: WARN when missing (an agent task: build it with create-verification-skill), stale,
  or without the Claude link.
- L4 (Stop and SubagentStop, adopted repos): router walls `verify-tool-exists` (ticket 02: app code changed in the turn,
  no verify skill or one without a valid run) and `verify-tool-used` (ticket 03: app code changed, no valid log in
  this checkout that finished after the first change). The change is read from git in the agent's checkout (a
  linked worktree too), so shell writes count. Loop limits: 2 blocks per app-code state, 4 per chain. Details:
  `ai/marketplace/plugins/ai-core/hooks/README.md`.
- L4 (git pre-commit, every writer): `ai-precommit` refuses a commit whose staged diff adds a test (Python
  `def test_...(`, `test(` or `it(` in a JS or TS spec file) in a project with a verify skill, when no valid log of
  this checkout finished after HEAD's commit time (ticket 04; wall `verify-commit`). Edits and deletions of tests
  pass.
- Planned (spec `docs/specs/verify-enforcement.md`): ticket 05, the PR gate on `gh pr create`, `edit` and `ready`
  that needs a valid log at the PR head SHA. All hooks read the log contract above (`hooklib.verify_runs`).
- Text: Done item 1 in the repo AGENTS.md. The root AGENTS.md carries nothing extra (hooks over text).

## Proof
- Should fire (EN): "add a discount field to checkout" in a repo with a web UI and no verify skill: the agent runs
  create-verification-skill first, writes `.agents/skills/verify-<app>/` with a feature map and proves it with one
  run; "verify the checkout change before you say done" in a project that has one: the agent runs `verify-<app>`
  on the checkout feature and saves evidence.
- Should fire (RO): "verifica schimbarea de la cos cu skill-ul de verificare inainte sa termini".
- Should fire (RU): "проверь изменение корзины навыком проверки, прежде чем закончить".
- Should not fire: "fix the typo in the README" (no code edit, no hint); a library-only repo.
- Signal: Skill or Read of `create-verification-skill` or `verify-<app>`, `.verify/evidence/<run>/run.log`,
  `[ai router: verify-before-done]`. Tests: `ai/tests/test_tier1.py` (`t_verify_*`, `t_pstack_adapt_ours`,
  `t_adopt_verify_link`, `t_typed_only_skill_paths`), `ai/tests/cases/verify-before-done.json`, `pr-rules.json`,
  `test_resolve.py` (`t_bash_pstack`), `cases/verify-tool-exists.json`, `cases/verify-tool-used.json`, `test_flow.py`
  (`t_vh_*`: the hooks and the commit gate, the worktree regression).), `test_flow.py` (`t_pr_gate_*`), `test_skills.py`
  (`t_release_runs_maintain`).

## Setup checklist
- Install: `install.sh` links `ai/skills/create-verification-skill` and `ai/skills/maintain-verification-skill`
  into `~/.claude/skills` and `~/.agents/skills` (like every own skill). `PSTACK_SOURCE` in `ai/pins.env`: when
  upstream moves, `pstack_src` clones, checks for symlinks, adapts (`ai/lib/pstack_adapt.py`), runs `agent-audit
  dir`, installs into the plugin source dir and `pstack_link` points the links there; the run warns that the
  vendor copy is behind (review the diff, refresh `ai/rules/vendor/pstack-verification` and `ai/skills`).
  Hermes: not wired (UNVERIFIED for Hermes).
- Keys, telemetry, network: none (the generated project skill may start the app locally).
- Per project: nothing for the owner. The agent runs `create-verification-skill` at the first feature task,
  commits `.agents/skills/verify-<app>/` and `.verify/` in `.gitignore`, and runs `ai-adopt` (the `.claude`
  link). The `.gitignore` block shares `.claude/skills/verify-*`.
- Verify: `ls ~/.claude/skills/create-verification-skill/SKILL.md ~/.agents/skills/maintain-verification-skill/SKILL.md`;
  `ai-doctor --project <repo>` shows the verify skill line.
- Cleanup: remove the two links; delete `<plugin src>/pstack-verification`; per project delete
  `.agents/skills/verify-<app>/` and the `.claude` link.
