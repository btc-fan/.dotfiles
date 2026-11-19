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
  worktree root). `<run>` is `<branch>_<feature>_<DD-MM-YYYY>_<HH-MM-SS>` (UTC), for example
  `fix-cart-total_checkout_18-11-2026_14-30-05`. The project
  `.gitignore` ignores `.verify/` except `.verify/evidence/` (the `ai-adopt` block). Cleanup keeps the evidence.
- Each run folder is committed on the feature branch with the change it proves, with a `summary.md` and no secrets
  (verify-evidence-in-git, owner 2026-11-19). The owner reads it on GitHub from any machine.
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

## Why a run log, and where the idea comes from (owner 2026-11-18)

The owner rule: the AI validates each change on the real app with the project's verify tool, then automates the
test. The owner does not check this by hand, so a hook must check it. A hook cannot see what the agent did in its
session. It can only read files and git. So the verify tool leaves one small trace on disk: `run.log`. The 4 lines
answer one question: "did the agent run the verify tool on this code, on a healthy app, without faked steps,
after its last change?" The evidence itself (response bodies, screenshots, DB reads) stays next to the log for a
reviewer. The run folder, the log included, is
committed with the PR. A commit that changes only `.verify/evidence/` does not move the proven code:
`hooklib.code_head` skips it for hooks 3 and 4.

How the 4 hooks use it (the walls in `ai/marketplace/plugins/ai-core/hooks/README.md`):
1. Hook 1, `verify-tool-exists` (Stop, SubagentStop): app code changed in the turn, and the project has no verify
   skill with one valid run. The agent must build the tool and prove it once.
2. Hook 2, `verify-tool-used` (Stop, SubagentStop): app code changed in the turn, and no valid run finished after
   the last change (owner 2026-11-18: the last change, so a change after a run needs a new run). The change is read
   from git in the agent's own checkout, so shell writes and worktrees count.
3. Hook 3, `verify-commit` (`ai-precommit`, every writer): a commit that adds a test needs a valid run that
   finished after HEAD's commit time.
4. Hook 4, `verify-pr` (`gh pr create`, `gh pr edit` with a body, `gh pr ready`): a PR that changes app code needs
   a valid run at the PR head commit.

Example: an agent edits `src/billing.py` and writes `tests/test_billing.py`. Hook 2 blocks the end of its turn.
The agent runs `verify launch`, `verify doctor`, `verify drive billing`, `verify cleanup`; the helper writes
`run.log` with the HEAD sha, `doctor: PASS`, `db_writes: no` and the end time. The turn ends. `git commit` passes
hook 3 because the run is newer than HEAD. `gh pr create` passes hook 4 when a run exists at the PR head.

Sources and what we took from each:
- pstack, the original generator (MIT): https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md
  and `maintain-verification-skill`. Took: launch, doctor, drive, evidence, cleanup; "a generated skill that was
  never executed is a draft"; evidence survives cleanup; a feature map with 4 sections per feature. pstack has no
  enforcement: its `principle-prove-it-works` skill is text ("apply after completing a task, before declaring done").
- The worked example, verify-atlas: https://github.com/poteto/verification-skill-example (`.cursor/skills/verify-atlas/SKILL.md`).
  Took: the proof bar (success, cancel, error, empty, persistence paths; unreachable paths named with the blocker),
  a doctor that knows its checkout, a full sweep order and a journeys file. No enforcement: a reviewer reads the
  evidence.
- kody, a real project: https://github.com/kody-hq/kody/blob/main/.agents/skills/control-kody/SKILL.md, plus
  `visual-recap` and `preview-manual-test` in the same folder. Took: one CLI per project, local verification first,
  "CI green is not enough for a user-visible change", proof after deploy. kody enforces one thing in CI (every
  route has a feature file) and leaves the proof itself to the agent and the reviewer.
- Claude Code hooks: https://code.claude.com/docs/en/hooks. Hooks run for subagents; `cwd` follows a worktree;
  a Stop or SubagentStop hook can block the end of a turn. "A prompt alone can't guarantee" a rule
  (https://code.claude.com/docs/en/best-practices). Codex hooks: https://developers.openai.com/codex/hooks, "a
  useful guardrail, not a complete enforcement boundary".
- Anthropic, https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents: agents mark
  features done "without proper testing"; the fix is to "do all testing as a human user would".

What is ours, not in the sources: the run log and the 4 hooks. The references trust the agent and a reviewer.
This setup has no human reviewer for each run, so a hook checks for the trace. Limits: a hand-written `run.log`
passes the hooks, and the hooks never judge if the drive was good; code review and the ship skill do.

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
  this checkout that finished after the last change). The change is read from git in the agent's checkout (a
  linked worktree too), so shell writes count. Loop limits: 2 blocks per app-code state, 4 per chain. Details:
  `ai/marketplace/plugins/ai-core/hooks/README.md`.
- L4 (git pre-commit, every writer): `ai-precommit` refuses a commit whose staged diff adds a test (Python
  `def test_...(`, `test(` or `it(` in a JS or TS spec file) in a project with a verify skill, when no valid log of
  this checkout finished after HEAD's commit time (ticket 04; wall `verify-commit`). Edits and deletions of tests
  pass. Owner skip: `sudo ai-gate-skip verify-commit <minutes> <why>`.
- L4 (PreToolUse, pr-rules): the PR gate on `gh pr create`, `edit` and `ready` needs a valid log at the PR head SHA
  (ticket 05; wall `verify-pr`). All hooks and the verify-ai-setup tool read the log contract above
  (`hooklib.verify_runs`).
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
  (`t_vh_*`: the hooks and the commit gate, the worktree regression; `t_pr_gate_*`: the PR gate), `test_skills.py`
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
  commits `.agents/skills/verify-<app>/`, and runs `ai-adopt` (the `.claude` link and the `.gitignore` block,
  which also drops an old bare `.verify/` line). The `.gitignore` block shares `.claude/skills/verify-*`.
- Verify: `ls ~/.claude/skills/create-verification-skill/SKILL.md ~/.agents/skills/maintain-verification-skill/SKILL.md`;
  `ai-doctor --project <repo>` shows the verify skill line.
- Cleanup: remove the two links; delete `<plugin src>/pstack-verification`; per project delete
  `.agents/skills/verify-<app>/` and the `.claude` link.

## Evidence cleanup (verify-evidence-in-git)
- `ai-evidence-prune` removes committed run folders older than 7 days and keeps the newest run of each feature.
  It refuses main and master. It does not commit.
- Trigger: the `merge-review` session-start note, when the repo tracks `.verify/evidence/`. The agent runs it on a
  branch `chore-prune-evidence-<date>` and opens a PR. The owner merges.
- Git history keeps the removed files (about 1 MB per run). Tests: `ai/tests/test_evidence.py`,
  `test_commands.py` (`t_merged_branches_note`).
