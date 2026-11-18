# Spec: verify before automate, enforced

Status: agreed with the owner on 2026-11-18 (grilling session, rounds 1 to 4). Branch `verify-enforcement`.

## Problem Statement

The owner only guides. The AI must build, check and prove its own work. The setup has a tool for proof: a project verification skill `verify-<app>` that launches the real app, drives it like a user and keeps evidence. The owner rule is: an agent may write tests first, but it must drive each test case once through `verify-<app>` on the real app before it automates the test.

In real work this rule does not hold:

1. Only 1 of 8 adopted projects has a verify skill (ScripTube). radar999, milu and 999-agent-claude have the Done text "verify-<app>, then e2e", but no skill to call.
2. The generator `create-verification-skill` is typed-only, and `rules/verification-skill.md` says "Never generate a verify skill for a project without the owner asking". So the AI cannot make the tool.
3. The generator tells the AI to "pick the primary" surface. A project with an API and a UI gets one of them.
4. In ScripTube PR #25 (30 tickets): 17 tickets drove the app before the first test, 7 wrote tests first, 6 had no proof made with the verify skill. Some proofs inserted rows with SQL, which the skill forbids.
5. Nothing blocks. `verify-before-done` is a nudge, once per session, and the main agent and all subagents share it. The PR check reads words in the PR body, only on `gh pr create`.
6. ScripTube's own test gate (its PR #13) reads the root of the main checkout. Subagents worked in worktrees, so the gate never fired. Reproduced on 2026-11-18: the same new-test write exits 2 on the main checkout and 0 in a worktree.
7. `ai-adopt` writes the Done block only when the project has no Done section. ScripTube has its own, so the verify step never reached it.

## Solution

Keep the tools. Make the AI build the verify tool in every project, make it cover every surface, and enforce its use with hooks at 4 points. A hook only looks for fresh tool logs; it never needs labels or a record file.

- The generator stays the pstack text. The adapter changes 2 sentences and appends one "Our additions" section.
- Each project has its own `verify-<app>`. It grows with the project: a feature change updates its feature file in the same PR.
- 4 hooks: the tool must exist, the tool must be used, a commit that adds tests needs fresh proof, a PR needs proof of its final tree.

## User Stories

1. As the owner, I want the AI to build `verify-<app>` itself, so that I never type `/create-verification-skill`.
2. As the owner, I want the AI to build the tool at the first feature task in a project that has none, so that no feature ships without a way to prove it.
3. As the owner, I want that first task to wait until the tool passed one real run, so that a draft tool never counts.
4. As the owner, I want the tool to cover every surface the project has (HTTP API, web UI, CLI, workers), so that a change on any surface can be proven.
5. As the owner, I want a web UI with 3 or more pages to have a Playwright mode in the tool, so that UI flows are driven in a real browser.
6. As the owner, I want mobile drivers (Maestro) only when a mobile project needs them, so that the setup stays small.
7. As an agent, I want each feature file to list the success, cancel, error, empty and persistence paths, so that I know what a full proof drives.
8. As an agent, I want unreachable paths named with what blocks them, so that a gap is visible and not hidden.
9. As an agent, I want a full sweep order in the feature map index and a journeys file for flows that cross surfaces, so that a broad regression run has a fixed order.
10. As an agent, I want `doctor` to know which checkout or worktree it runs in, so that I never drive an instance another run started.
11. As an agent, I want to update or add the feature file in the same PR as the feature, so that the map does not rot.
12. As an agent, I want to drive each test case through the tool before I automate it, so that the test encodes behavior I saw in the real app.
13. As the owner, I want a Stop and SubagentStop hook to block the end of a feature turn when the project has app code and no verify skill, so that the tool gets built.
14. As the owner, I want a Stop and SubagentStop hook to block the end of a turn when the agent changed app code and made no new tool log since the change, so that the tool gets used.
15. As the owner, I want that hook to read the change from git in the agent's own checkout, so that shell writes and worktrees are covered.
16. As the owner, I want the commit gate to refuse a commit that adds tests when no tool log is newer than the previous commit, so that every ticket commit carries fresh proof, for Claude, Codex, subagents and the shell.
17. As the owner, I want the PR gate (`gh pr create`, `gh pr edit`, `gh pr ready`) to require tool logs from a run on the PR head that are newer than the last code commit, so that the final merged tree is proven.
18. As the owner, I want a log to count only when `doctor` passed and the run made no direct SQL writes, so that faked steps do not count as proof.
19. As the owner, I want `maintain-verification-skill` to run by the AI inside `release` and when the session status says the map is stale, so that drift gets fixed without me.
20. As the owner, I want projects with their own Done section to get one managed verify line, so that the rule reaches every project and my text stays.
21. As the owner, I want the `verify-before-done` nudge per agent, not per session, so that each subagent gets it.
22. As the owner, I want ScripTube's own test gate removed in the pilot PR, so that one rule has one gate.
23. As the owner, I want the rollout in this order: dotfiles, ScripTube, milu, radar999, one PR each, so that I approve each merge.

## Implementation Decisions

- Generator. The adapter keeps the pstack text word for word, with 3 kinds of change: (a) the existing path and dash transform; (b) 2 sentence replacements: the typed-only flag goes, and "pick the primary one and note the rest" becomes "cover every surface"; (c) one appended "Our additions" section: every surface with its driver, the atlas proof set (success, cancel, error, empty, persistence, named unreachable paths), worktree-aware doctor, full sweep order, journeys file, feature file in the same PR, evidence in `.verify/evidence/` in the repo folder (gitignored), and the log fields the hooks read. The maintain skill gets the same flag change.
- Drivers per surface: HTTP helper for APIs and form posts; Playwright for a web UI with 3 or more pages (the project turns on the browser tool); PTY or tmux for a CLI; a job trigger plus a read of the stored state for workers. Maestro is named only, not installed.
- Rule text: `rules/verification-skill.md` is rewritten. The AI makes the tool; the owner never types the generator. The session status line changes from an owner step to an agent task.
- Evidence log contract (read by the hooks): one folder per run under `.verify/evidence/<run>/`, with a log that records the commit SHA, the doctor result, and whether the run wrote to the database directly. The generator tells each project helper to write these fields.
- Hook 1 (tool exists): a Stop and SubagentStop rule. Trigger: a turn that edited app code, in a project with app code and no verify skill. Proof: a verify skill folder with a SKILL.md and one evidence run.
- Hook 2 (tool used): a Stop and SubagentStop rule. Root: the git top level of the agent's cwd. Trigger: app code differs from the turn's start (git, not tool calls). Proof: a valid log newer than the first change.
- Hook 3 (commit gate): a new step in `ai-precommit`. Trigger: the staged diff adds a test function or spec, and the project has a verify skill. Proof: a valid log newer than HEAD's commit time.
- Hook 4 (PR gate): `pr_verify_evidence` runs on create, edit and ready. Root and HEAD come from the checkout the command names. Proof: a valid log at the PR head SHA, newer than the last code commit.
- Valid log: doctor PASS and no direct SQL writes. The hooks never judge proof quality; code review and the ship skill do.
- Done line: `ai-adopt` adds one managed `AI:verify` block under a project's own Done section. Projects without one keep the full managed Done block.
- Nudge: `verify-before-done` keys on the agent id, so each subagent gets it once.
- Maintain: the `release` skill runs it; a stale status line tells the agent to run it.
- No map check in CI. No labels on tests. No committed record file.

## Testing Decisions

- A good test drives the hook or tool the way an agent session does: a hook payload or a git state in a fixture repo, then the exit code and the message. It never calls internal helpers.
- Seams, highest first: (1) the router and hooklib with JSON hook payloads on fixture repos (prior art: `ai/tests/cases/*.json`, `t_verify_*` in `test_tier1.py`); (2) `ai-precommit` on a fixture repo with staged files; (3) `pstack_adapt.py` on the vendor copy (prior art: `t_bash_pstack`); (4) `ai-eval scenario` for the end to end run (prior art: the evolution scenario).
- Regression: the worktree case. A new test written in a linked worktree must be blocked by hook 2 and hook 3. This is the loop that reproduced the ScripTube bug.
- Each hook gets a red case (blocks) and a green case (passes with a valid log), plus the invalid-log case (doctor FAIL, SQL write).

## Out of Scope

- Mobile drivers beyond naming Maestro.
- A feature map check in CI (kody `map --check`).
- Labels that link each test to one run, and a committed record of runs.
- Pixel baselines; they come with the Playwright work in a later spec.
- kody's risk classes and visual recap.

## Further Notes

- Sources read in full: pstack `create-verification-skill` and `maintain-verification-skill` with the feature map example; `poteto/verification-skill-example` (verify-atlas); kody `control-kody`, `visual-recap`, `preview-manual-test`; Claude Code and Codex hook docs; Playwright and Maestro docs.
- Known limit: the hooks prove the scenario was driven before the commit, not before the test was written. This matches the owner rule.
- Known limit: `git commit --no-verify` skips hook 3. The no-verify gate already blocks agents from it.
- ScripTube note: proofs live in each ticket worktree and go away with it. The PR gate reads the final run on the PR head, so this is accepted.

## Addendum: hook 2 timing (owner 2026-11-18)

Hook 2 needs a valid run that finished after the LAST app-code change of the turn, not the first. A change made after a verify run needs a new run.

## Addendum: walls review (owner grilling 2026-11-18)

The new hooks add walls, so every existing wall was measured first: 3 machines, 7 days, real sessions only. Decisions:

- Keep and fix: secret-scan (ticket 11; about 25 blocks, 14 of 14 sampled were test values), merge-approval (ticket 12; 17 blocks, 14 false), pr-rules (ticket 13; about half false, `$VAR` body files).
- Keep as is: nav-first (deny once per session, no deny after graphify or Serena was used), no-verify, gh-write, writing-for-agents, ship, stop-check.
- Hints instead of stops: diagnosing-bugs and tdd (ticket 14; 7 of 7 false).
- Off: OMC magic keywords and the OMC context-guard stop (ticket 15).
- Bugs, not rules: Playwright refused on dev-mac against the owner decision of 2026-11-14, the ai-adopt branch collision, Python tests missed without pyproject.toml (ticket 16).
- Measure: every wall logs its fires; `ai-doctor` shows 7 days; a verify hook with more than 1 in 3 false fires becomes a hint (ticket 17).
- Every kept rule runs as a hook (PreToolUse, Stop, SubagentStop, git pre-commit), never as text only.
