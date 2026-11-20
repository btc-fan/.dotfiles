# How Matt Pocock gets agents to follow rules, and how our hook setup compares

Research date: 2026-11-20. Read-only. Sources were downloaded as tarballs and read as data only.

- mattpocock/skills, branch `main`, pushed 2026-11-19T13:35Z, plugin version 1.3.2 (`.claude-plugin/plugin.json`). 187 files.
- mattpocock/course-video-manager (CVM), branch `main`, pushed 2026-11-19T07:53Z. 2923 files.
- Our side: `<setup>`, branch `ai`, commit `443536f` (2026-11-20 11:26 +0200).

Local copies: `plan-research/skills-dl/`, `plan-research/cvm-dl/` (same folder as this file). Raw inventory: `plan-research/skills-inv.txt`, `plan-research/hookfuncs.txt`.

## A. mattpocock/skills inventory

### A.1 Repo layout

- Buckets under `skills/`: `engineering/` (20), `productivity/` (7), `misc/` (4, frozen), `in-progress/` (8, beta), `deprecated/` (README only). Total 39 skills.
- "Promoted" = `engineering/` + `productivity/` = 27 skills. Only these ship in the plugin (`.claude-plugin/plugin.json` `skills` array has exactly 27 paths).
- `CLAUDE.md`: 33 lines, 559 words. `AGENTS.md` is a symlink to `CLAUDE.md`. Content: repo maintenance rules only (bucket rules, README and plugin.json must list promoted skills, docs page per promoted skill, invocation split, "No em-dashes anywhere in this repo's prose", "Every skill that dispatches a subagent says to start it with a fresh context window").
- `.agents/` (maintainer reference, reached by pointers from CLAUDE.md): `invocation.md` (26 l, 574 w), `writing-docs.md` (96 l, 2091 w), `install-block.md` (121 l, 641 w), `adr/0001`, `adr/0002`.
- `SCOPE.md` + `.out-of-scope/*.md` (9 files): every rejected idea with its reason.
- `docs/engineering/*.md`, `docs/productivity/*.md`: one human-facing page per promoted skill (27 pages), published on aihero.dev.
- `scripts/`: `check-frontmatter.mjs`, `link-skills.sh`, `list-skills.sh`, `sync-plugin-version.mjs`.

### A.2 Skill table

Columns: lines and words of `SKILL.md`; invocation (`model` = model-invoked, description always loaded; `typed-only` = `disable-model-invocation: true`); all `.md` files in the skill folder (lines / words); non-Markdown files besides `agents/openai.yaml`.

| Skill | Bucket | SKILL.md lines | SKILL.md words | Invocation | All .md lines / words | Scripts or assets |
|---|---|---|---|---|---|---|
| ask-matt | engineering | 97 | 1958 | typed-only | 152 / 2657 | no |
| code-review | engineering | 89 | 1094 | model | 89 / 1094 | no |
| codebase-design | engineering | 114 | 851 | model | 195 / 1635 | no |
| diagnosing-bugs | engineering | 138 | 1427 | model | 138 / 1427 | scripts/hitl-loop.template.sh |
| domain-modeling | engineering | 74 | 493 | model | 181 / 1260 | no |
| grill-with-docs | engineering | 7 | 35 | typed-only | 7 / 35 | no |
| implement-spec | engineering | 42 | 445 | typed-only | 42 / 445 | no |
| implement | engineering | 17 | 103 | typed-only | 17 / 103 | no |
| improve-codebase-architecture | engineering | 71 | 904 | typed-only | 194 / 1828 | no |
| pr | engineering | 170 | 568 | model | 173 / 654 | no |
| prototype | engineering | 26 | 487 | model | 205 / 2630 | no |
| research | engineering | 12 | 138 | model | 12 / 138 | no |
| retro | engineering | 44 | 679 | typed-only | 44 / 679 | no |
| setup-matt-pocock-skills | engineering | 120 | 1126 | typed-only | 312 / 3165 | no |
| tdd | engineering | 38 | 574 | model | 174 / 1067 | no |
| to-spec | engineering | 75 | 493 | typed-only | 75 / 493 | no |
| to-tickets | engineering | 105 | 917 | typed-only | 105 / 917 | no |
| triage | engineering | 112 | 990 | typed-only | 424 / 2936 | no |
| wayfinder | engineering | 128 | 2080 | typed-only | 128 / 2080 | no |
| wizard | engineering | 44 | 673 | model | 44 / 673 | template.sh |
| chief-of-staff | in-progress | 75 | 747 | typed-only | 75 / 747 | no |
| claude-handoff | in-progress | 18 | 222 | typed-only | 18 / 222 | no |
| loop-me | in-progress | 32 | 415 | typed-only | 32 / 415 | no |
| setup-ts-deep-modules | in-progress | 102 | 1110 | typed-only | 102 / 1110 | dependency-cruiser.config.cjs |
| software-factory | in-progress | 98 | 946 | typed-only | 516 / 6377 | no |
| writing-beats | in-progress | 67 | 852 | typed-only | 67 / 852 | no |
| writing-fragments | in-progress | 79 | 595 | typed-only | 79 / 595 | no |
| writing-shape | in-progress | 79 | 1026 | typed-only | 79 / 1026 | no |
| git-guardrails-claude-code | misc | 95 | 302 | model | 95 / 302 | scripts/block-dangerous-git.sh |
| migrate-to-shoehorn | misc | 118 | 415 | model | 118 / 415 | no |
| scaffold-exercises | misc | 106 | 442 | model | 106 / 442 | no |
| setup-pre-commit | misc | 91 | 332 | model | 91 / 332 | no |
| grill-me | productivity | 7 | 22 | typed-only | 7 / 22 | no |
| grilling | productivity | 30 | 333 | model | 30 / 333 | no |
| handoff | productivity | 16 | 144 | typed-only | 16 / 144 | no |
| teach | productivity | 140 | 1522 | typed-only | 284 / 2815 | no |
| to-questionnaire | productivity | 54 | 470 | typed-only | 54 / 470 | no |
| wait-what | productivity | 7 | 60 | typed-only | 7 / 60 | no |
| writing-for-agents | productivity | 81 | 1777 | model | 103 / 2191 | no |

### A.3 Totals and always-loaded cost

- Promoted set: 27 skills. 11 model-invoked, 16 typed-only.
- Model-invoked promoted skills: prototype, diagnosing-bugs, research, tdd, domain-modeling, codebase-design, code-review, pr, wizard, grilling, writing-for-agents.
- Always-loaded cost of the promoted set in Claude Code: the 11 model-invoked descriptions = **334 words (2156 characters)**, about 345 words with the names. The 16 typed-only descriptions (297 words) are for the human slash menu. Per `.agents/invocation.md` and `SKILL-MECHANICS.md`, they carry "Zero context load".
- Longest descriptions: code-review 68 words, wizard 47, to-tickets 41. Shortest: pr ("Use when writing a PR body.", 6 words).
- Body size: the 27 promoted `SKILL.md` files = 1858 lines, 20363 words. With the reference files beside them: 3212 lines, 31951 words. None of it loads until the skill fires.
- Smallest skills are pure handoffs: `grill-with-docs` (7 lines, 35 words: "Call the Skill tool twice, for "grilling" and "domain-modeling"."), `grill-me` (7 lines), `wait-what` (7 lines), `research` (12 lines), `implement` (17 lines).
- Skills with scripts: diagnosing-bugs (`scripts/hitl-loop.template.sh`), wizard (`template.sh`), setup-ts-deep-modules (in-progress, `dependency-cruiser.config.cjs`), git-guardrails-claude-code (misc, `scripts/block-dangerous-git.sh`).

### A.4 How skills get into a project

- Managed install, read-only and auto-updating: `claude plugin install mattpocock-skills@claude-plugins-official` (README "Installation"). ADR 0002: the official listing pins a sha, so "a release reaches installed users when that pin moves".
- Editable copies: `npx skills@latest add mattpocock/skills`. The two routes "are exclusive" (`.agents/install-block.md`).
- Per repo, once: `/setup-matt-pocock-skills` (typed-only). It explores, asks one section at a time, then writes `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, optionally `docs/agents/triage-labels.md`, and an `## Agent skills` block of 3 one-line pointers into `CLAUDE.md` (or `AGENTS.md`). Its own words: "This is a prompt-driven skill, not a deterministic script."
- ADR 0001: only hard-dependency skills (`to-tickets`, `to-spec`, `triage`) carry the pointer "run `/setup-matt-pocock-skills` if not". Soft-dependency skills mention the glossary and ADRs "in vague prose only", to stay "token-light".

### A.5 Handoffs between skills

The rule (`.agents/invocation.md`): "Dependencies are expressed as an explicit instruction to **call the Skill tool** with the named skill". The reason: "Naming the tool is what gets it fired". A typed-only skill can call model-invoked skills, never another typed-only skill. When a step needs a typed-only skill, the text tells the human: "tell the user to run `/setup-matt-pocock-skills`".

| From | To (Skill tool call) | Quote |
|---|---|---|
| grill-with-docs | grilling + domain-modeling | "Call the Skill tool twice, for "grilling" and "domain-modeling"." |
| grill-me | grilling | "Call the Skill tool with "grilling"." |
| implement | tdd, then code-review | "Call the Skill tool with "tdd" where possible, at pre-agreed seams." / "Once done, call the Skill tool with "code-review"" |
| implement-spec | tdd (per implementer subagent), code-review | "calls the Skill tool with `tdd` to build the ticket" |
| tdd | codebase-design | "call the Skill tool with "codebase-design" for the vocabulary" |
| improve-codebase-architecture | codebase-design, grilling, domain-modeling | "call the Skill tool with "grilling" to walk the decision tree" |
| triage, wayfinder | grilling + domain-modeling, research, prototype | wayfinder: "Resolved by a subagent that calls the Skill tool with "research"." |
| retro | writing-for-agents | "Call the Skill tool with `writing-for-agents` for the writing style guide." |
| handoff | (names skills for the next agent) | "Include a "suggested skills" section" |

The typed chain (human types each step): `grill-with-docs -> to-spec -> to-tickets -> implement (or implement-spec) -> code-review`, then `/retro` (`.agents/writing-docs.md`, "Where it fits"). `ask-matt` (typed-only, 97 lines) is the router for the human.

### A.6 What is NOT in the skills repo

- No `.claude/settings.json`, no hooks, no permission rules, no agent gate of any kind in the promoted set.
- The only hook is in a frozen `misc/` skill: `git-guardrails-claude-code` installs a PreToolUse hook. Its known bypass stays open: issue #301 "`block-dangerous-git.sh` is bypassed by any git global option (e.g. `git -C <dir> push`)" was closed as out of scope (`.out-of-scope/frozen-misc-skills.md`).
- CI for behaviour: none. `.github/workflows/check.yml` runs only `npm run check-frontmatter` (YAML parse of each `SKILL.md`, `name` and `description` present). The other 3 workflows are release and issue-label bots.
- No eval. `docs/productivity/writing-for-agents.md`: "There is no automated eval. You check by running the document by hand".
- No em-dash lint, although `CLAUDE.md` bans em dashes. (Count in `CLAUDE.md`: 0.)
- No GitHub ruleset visible (`gh api repos/mattpocock/skills/rulesets` returned an empty list).
- Explicitly rejected: guards against subagent recursion ("The harness should be responsible for stopping infinite subagent loops, not skills"), hard question limits, a native question tool, a verify mode for setup.

## B. His enforcement model

| Mechanism | Example 1 (quote, file) | Example 2 (quote, file) |
|---|---|---|
| Skill description wording (model-invoked trigger) | tdd: "Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants integration tests." (`skills/engineering/tdd/SKILL.md:3`) | diagnosing-bugs: "Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow." (`skills/engineering/diagnosing-bugs/SKILL.md:3`) |
| Typed slash command (no model reach) | "User-invoked: reachable **only by the human typing its name**." (`.agents/invocation.md`) | "Pick model-invocation only when the agent must reach the skill on its own, or another skill must. If it only ever fires by hand, make it user-invoked and pay no context load." (`writing-for-agents/SKILL-MECHANICS.md:12`) |
| Explicit Skill tool handoff | "Call the Skill tool with "tdd" where possible, at pre-agreed seams." (`implement/SKILL.md:11`) | "Once all tickets are complete, call the Skill tool with `code-review` on the integration branch." (`implement-spec/SKILL.md:38`) |
| Step with a completion criterion | "Phase 1 is done when the loop is **tight** and **red-capable**: you can name **one command** ... that you have **already run at least once**" and "No red-capable command, no Phase 2." (`diagnosing-bugs/SKILL.md:59,66`) | "The session is done when the frontier is empty ... Do not act on it until the user confirms you have reached a shared understanding." (`grilling/SKILL.md:30`) |
| A file the skill must write | "write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md` ... never a single combined file." (`to-tickets/SKILL.md:62`) | "Record the choice in `docs/agents/issue-tracker.md`." plus the `## Agent skills` block (`setup-matt-pocock-skills/SKILL.md:49,86`) |
| Human review point | "Iterate until the user approves the breakdown." (`to-tickets/SKILL.md:56`) | "Before writing any test, write down the seams under test and confirm them with the user. No test is written at an unconfirmed seam." (`tdd/SKILL.md:22`); also "**Show the ranked list to the user before testing.**" (`diagnosing-bugs/SKILL.md:98`) |
| Tests as the feedback loop | "**Red before green.** Write the failing test first" (`tdd/SKILL.md:36`) | "Run typechecking regularly, single test files regularly, and the full test suite once at the end." (`implement/SKILL.md:13`) |
| CI | skills repo: `check.yml` runs only the frontmatter check. | CVM: ruleset "main: up-to-date and green before merge" (active) plus `test.yml` (`docs/agents/merging.md`: "The ruleset is the only gate, and it holds for agents without exception"). |
| Lint / deterministic checks | "a **mechanical** one ... gets a deterministic check, full stop ... Default to building the check over writing the rule." (`retro/SKILL.md:19`) | Deep modules: "use a linter like dependency-cruiser to forbid imports that bypass the interface" (`docs/engineering/codebase-design.md:52`). CVM runs it in `lint:boundaries`. |
| Agent hooks | `git-guardrails-claude-code` (misc, frozen, known bypass). | CVM: one PreToolUse hook, `.claude/hooks/block-npx-tsc.sh` (12 lines): "Use `pnpm run typecheck` instead of `npx tsc`". |
| Reviewer, not implementer, carries standards | "the review agent should be responsible for imposing coding standards, not the implementation agent." (`retro/SKILL.md:35`) | code-review "Standards" axis reads `CODING_STANDARDS.md` "or `CONTRIBUTING.md`" in a fresh subagent (`code-review/SKILL.md:36`). |

### What he leaves to the human

- Typing 16 of 27 skills. The human is "the index" (`.agents/writing-docs.md`). The router `ask-matt` only hints.
- Approval points: seams (tdd, to-spec), ticket breakdown (to-tickets), the ranked hypotheses (diagnosing-bugs), "shared understanding" (grilling), the draft config (setup).
- Strict compliance. `docs/engineering/tdd.md:58`: "No instruction makes an agent comply 100% of the time, and stricter wording restricts the agent's creativity for little gain ... watch the run rather than trusting the skill to enforce it."
- Which checks become permanent. `docs/engineering/retro.md:35`: "`retro` only proposes ... installs no hook automatically." A user had been "burned by auto-hooks that blocked good changes."
- Pruning checks: "You must still prune checks yourself. A rule that fires constantly on good code is the sign to remove it." (`docs/engineering/retro.md:39`)
- Stopping a grilling or forbidding early build. `docs/productivity/grilling.md:61`: "the reliable fix is a line in your own `AGENTS.md` or `CLAUDE.md` telling the agent not to implement without permission."
- In CVM: merging migration PRs ("agents never merge a PR that touches `packages/core/db/migrations/` ... Matt merges it", `docs/agents/merging.md`), and ruleset bypass ("reserved for the human admin").

## C. course-video-manager

### C.1 Inventory

| Item | Size or count | Kind of content |
|---|---|---|
| `CLAUDE.md` (root, only one; no nested CLAUDE.md or AGENTS.md; no AGENTS.md at all) | 81 lines, 1644 words, 12 `###` sections, 30 em dashes | Pointers (backlog, merging, triage labels, domain docs, verify skill) plus large reference blocks: dev logs, repo layout, testing, checks, coding standards pointer, deep modules, a 509-word one-line "cvm CLI" section. 55 commits touch it (2025-10-21 to 2026-11-03). |
| `CODING_STANDARDS.md` | 415 lines, 3288 words, 24 `###` rules | Read in review (and "while writing code"). About 14 of 24 rules name the check that enforces them ("Enforced by type-aware oxlint", `scripts/check-*`). |
| `GLOSSARY.md` | 576 lines, 3380 words | Domain language, written by grill-with-docs / domain-modeling. |
| `docs/adr/` | 63 ADRs (two numbers reused: 0008, 0043) | Decisions. |
| `docs/agents/` | 7 files: `backlog.md` 160 w, `domain.md` 266 w, `merging.md` 638 w, `queued-promotion.md` 429 w, `testing.md` 687 w, `triage-labels.md` 241 w, `afk-agent-platform-spec.md` 7354 w; plus `prompts/` | Setup output of `/setup-matt-pocock-skills` plus his own process docs. |
| Other docs | `docs/TESTING_STANDARDS.md`, `EFFECT_STANDARDS.md`, `DRAFT_GUARD.md`, `FRONTEND_STATE.md`, `KEYBOARD_SHORTCUTS.md`; `docs/research/` 3 files, `docs/plans/` 5 files; `plans/backlog/` 8 files (an older ralph loop) | Disclosed reference. |
| `.claude/settings.json` | 1 PreToolUse hook (Bash), no permissions block | `block-npx-tsc.sh`, exit 2 with "Use `pnpm run typecheck` instead of `npx tsc`". |
| `.claude/skills/` (project skills) | 9: verify-cvm (417 l, 3193 w, 5 scripts, 7 feature files), deploy-migration (112 l), to-issues-project (136 l), improve-codebase-architecture-project (132 l), to-prd-project (86 l), optimize-loader (79 l), document-ai-hero-api (58 l, typed-only), do-work (29 l), install-effect-package (22 l) | 8 model-invoked, 1 typed-only. Model-invoked descriptions: about 346 words. |
| `.agents/`, `.cursor/`, `.codex/` | none | |
| Matt's own skills in the repo | none checked in | Installed outside the repo (could not confirm how). |
| `.sandcastle/` | 25 files: prompts and TypeScript runners for AFK agents in Docker (implement, implement-prd, implement-pr, review, to-issues-prd, architecture-review, update-branch, write-pr, merge) plus 4 test files | CI agents driven by GitHub labels. |
| `.github/workflows/` | 9: `test.yml` (job `check`), 7 `agent-*.yml` label triggers, `architecture-review.yml` (cron "0 9 * * 1-5") | CI and AFK agents. |
| GitHub ruleset | 1 active: "main: up-to-date and green before merge" | The only hard merge gate. |
| Git hooks | `.husky/pre-commit`: 20 commands (lint-staged prettier, typecheck, lint:boundaries, 17 guard scripts) | Fast half of `check`. |
| `package.json` scripts | `check` = `check:static` + `test` + `check:client-build`; 19 `scripts/check-*` files; `lint` = `oxlint --type-aware` (9 error rules, 4 warn, 19 off); 6 dependency-cruiser configs | Lint, type and test tooling. |
| Tests of the agent tooling | `tests/verify-cvm-*.test.ts` (5), guard tests (`complexity-guard`, `effect-guards`, `frontend-state-guard`, `background-jobs-guard`), `.sandcastle/*.test.ts` (4) | Tests of scripts and guards. No LLM behaviour eval found. |

Staleness found: `CLAUDE.md:69` says "the five file guards", while `scripts/` has 19 `check-*` files and pre-commit runs 17 guard scripts.

### C.2 Rule or convention -> where it is enforced

Primary class first; my classification. Classes: (1) CI or GitHub settings, (2) git hook, (3) lint/type/test or runtime guard in code, (4) agent hook or permission setting, (5) instruction text only, (6) skill on demand.

| # | Rule or convention | Class | Where |
|---|---|---|---|
| 1 | Merge only when `check` is green on an up-to-date branch | 1 | GitHub ruleset; `test.yml` job `check` |
| 2 | Full test suite runs on every PR; agents run only targeted tests | 1 (+5) | `test.yml`; `CLAUDE.md` "Testing" |
| 3 | `check:response-body` runs in CI only | 1 | `check:static` in CI |
| 4 | No node builtin in the browser build | 1 (+3) | `check:client-build`, `vite.config.ts` |
| 5 | Architecture review runs on weekdays | 1 | `architecture-review.yml` cron, `.sandcastle/architecture-review/` |
| 6 | AFK agent refuses a sub-issue or an issue with an open PR | 1 | `agent-implement.yml` "Pre-flight refusal" steps |
| 7 | Dependents are promoted when a blocker closes | 1 | `agent-promote-queued.yml` |
| 8 | `Sandcastle` label = ready-for-agent | 1 (+5) | label triggers; `docs/agents/triage-labels.md` |
| 9 | Judgement standards checked on agent PRs | 1 (+5) | `agent-review.yml` runs `.sandcastle/review/prompt.md`, which feeds `CODING_STANDARDS.md` to Matt's code-review |
| 10 | Formatting | 2 | `.lintstagedrc` prettier |
| 11 | Typecheck with Effect diagnostics on commit | 2 (+3) | pre-commit `typecheck`, `check:effect-tsc` |
| 12 | Deep-module package boundaries | 2 (+3) | `lint:boundaries` (dependency-cruiser) |
| 13 | 17 file guards (no `__dirname`, guarded DB clients, fs writes, one toast, one duration format, entity links, routes folder ...) | 2 (+3) | pre-commit and `check:static --all` |
| 14 | Complexity max 15, shrink-only allowlist | 2 (+3) | oxlint `complexity`, `scripts/check-complexity.ts` |
| 15 | Exhaustive switch, throw only Errors, no floating promises | 3 | oxlint error rules (`.oxlintrc.json`) |
| 16 | A worktree never writes to a remote DB | 3 | runtime refusal, `packages/core/db/connection-guard.ts` |
| 17 | Writes to a Version go through the Draft guard | 3 | runtime `VersionNotDraftError`, tests |
| 18 | Windows processes start only through `guardWindows()` | 3 (+5) | runtime guard, exit 3 |
| 19 | Schema Version mismatch is refused; local-only commands refuse elsewhere | 3 | `cvm` CLI exit 6 and exit 7 |
| 20 | Use `pnpm run typecheck`, not `npx tsc` | 4 | `.claude/hooks/block-npx-tsc.sh` |
| 21 | Every change lands through a PR from a fresh worktree | 5 | `CLAUDE.md:9`, `docs/agents/merging.md` step 1 |
| 22 | Agents never merge a migration PR | 5 | `docs/agents/merging.md` |
| 23 | Never skip hooks (`--no-verify`, `HUSKY=0`) | 5 | `docs/agents/merging.md` |
| 24 | Commit trailer `Co-Authored-By` | 5 | `docs/agents/merging.md` step 2 |
| 25 | Poll loops get a timeout; logs stay in the worktree | 5 | `docs/agents/merging.md` "Waiting and polling" |
| 26 | Keep `cvm --help` and `GLOSSARY.md` in sync by hand | 5 | `CLAUDE.md:81` |
| 27 | About 10 of 24 coding standards (for example "Every `any` is a leak", "Redirect from the action, not from an effect") | 5 (+1 via review agent) | `CODING_STANDARDS.md` |
| 28 | Read GLOSSARY and ADRs before work | 5 | `.sandcastle/*/prompt.md`, `docs/agents/domain.md` |
| 29 | UI change checked in a browser before the PR, PR body says what you clicked or `No UI change` | 6 (+5) | verify-cvm skill; `CLAUDE.md:23` |
| 30 | Migration flow end to end | 6 | `deploy-migration` skill |
| 31 | Install Effect packages safely | 6 | `install-effect-package` skill |
| 32 | Slow loader fixes | 6 | `optimize-loader` skill |
| 33 | PRD and sub-issue format | 6 | `to-prd-project`, `to-issues-project` skills |
| 34 | Domain language upkeep | 6 | Matt `grill-with-docs` / `domain-modeling` (outside repo) |

Counts by primary class: (1) 9, (2) 5, (3) 5, (4) 1, (5) 8, (6) 6. Total 34.

Three examples each:
- (1) CI or GitHub: ruleset (row 1); `architecture-review.yml` cron (row 5); `agent-implement.yml` pre-flight refusals (row 6).
- (2) Git hook: prettier via lint-staged (row 10); `lint:boundaries` (row 12); the complexity ratchet (row 14).
- (3) Tooling or runtime guard: oxlint error rules (row 15); `connection-guard.ts` (row 16); `cvm` exit 6 and 7 (row 19).
- (4) Agent hook: only one exists, `block-npx-tsc.sh` (row 20). No permission rules.
- (5) Text only: no migration merge (row 22); never skip hooks (row 23); help text sync (row 26).
- (6) Skill on demand: verify-cvm (row 29); deploy-migration (row 30); install-effect-package (row 31).

Pattern: every irreversible or shared-state action (merge, DB write, migration, Windows process) has a non-agent gate (ruleset, runtime refusal) or a human. Process conventions stay text.

### C.3 Always-loaded instructions in CVM

- `CLAUDE.md`: 81 lines, 1644 words, 12 sections.
- 8 model-invoked project skill descriptions: about 346 words.
- If Matt's plugin is on: 11 model-invoked descriptions, 334 words (not confirmed for this repo).
- Hooks inject nothing; the one hook only blocks.
- Total: about 1990 words, or about 2320 words with the plugin.

Note the contrast with his own advice in `retro/SKILL.md:41`: `CLAUDE.md`/`AGENTS.md` "should be used incredibly sparingly, usually only for **navigation pointers** to other files". CVM `CLAUDE.md` is 3x the skills repo `CLAUDE.md` (559 words) and carries reference blocks and a stale count.

## D. His writing rules for agent documents, and where our always-loaded file breaks them

### D.1 The rules (from `skills/productivity/writing-for-agents/SKILL.md`, 81 lines, and `SKILL-MECHANICS.md`)

- Context load: "Every word of an always-loaded pointer costs on every turn, so it earns even harder pruning than the body". "Context load is the cost of always-loaded material ... spending tokens and attention whether or not it fires." Docs page: "Anything that applies in one session out of ten costs context load in the other nine."
- Pointers: "The pointer's _wording_, not its target, decides when the agent reaches the material". Rules: "Front-load the leading word", "One trigger per branch. Synonyms that rename a single branch are one branch written twice", "Cut identity the body already carries."
- Progressive disclosure: "inline what every branch needs, and push behind a pointer what only some branches reach."
- Sprawl: "a document simply too long, even when every line is live and unique. Attention thins across the excess".
- Completion criteria: "Every step ends on a **completion criterion**". Two levers: clarity ("A vague bound ... invites **premature completion**") and demand ("Every modified model accounted for" beats "produce a change list").
- Leading words: "a compact concept already living in the model's pretraining ... Repeated as a token, never as a sentence".
- Negation: "steering by prohibition drags the forbidden behaviour into context and makes it _more_ available ... Prompt the **positive** ... A prohibition earns its place only as a hard guardrail you cannot phrase positively; even then, pair it with the positive target".
- Single source of truth: "**Duplication** (the same meaning in more than one place) costs maintenance and tokens, and inflates a meaning's prominence".
- Environment as source of truth: "a document that restates it is a **cache** ... Leave the one-file, one-command lookups to the environment".
- No-ops: "an instruction the model already obeys by default pays load to say nothing ... delete the whole sentence rather than trim words from it."
- Sediment: "stale layers that settle because adding feels safe and removing feels risky".
- Invocation: typed-only skills cannot be reached by the model; "phrase it as an instruction for the human to act on".

### D.2 Our always-loaded load

- Source `ai/agents-md/*.md`: 13 files, 146 lines, 2517 words.
- Rendered `~/.config/ai/AGENTS.md` (symlink to `<setup>/ai/AGENTS.md`): 197 lines, 3206 words. It includes the L0 routing table (`L0.md`, 49 lines, 1088 words).
- Added each session: `~/.claude/CLAUDE.md` (72 words), the project `AGENTS.md`, hook text (skill card up to 1500 characters, router nudges), and every model-invoked skill description on the machine. This session listed roughly 140 skills (hand count of the session list, approximate).
- Compare: skills repo `CLAUDE.md` 559 words; CVM `CLAUDE.md` 1644 words.

### D.3 Ten concrete breaks

| # | File:line | Rule broken | Evidence |
|---|---|---|---|
| 1 | `ai/agents-md/50-pull-requests.md:3-18` | Single source of truth; environment cache | Restates the `pr` skill template, then restates what the `pr-rules` gate blocks ("The pr-rules gate blocks a PR without the Mermaid diagram ..."). The same meaning lives in 3 homes: the skill, this file, and the L0 row `pr-rules (gate)`. The gate already returns its own message when it fires. |
| 2 | `ai/agents-md/50-pull-requests.md:21-35` | Progressive disclosure; context load | 15 lines on the author-sessions block load every turn. Only the "create or update a PR" branch needs them. They belong behind a pointer (the `pr-rules` gate message, or a rules file). |
| 3 | `ai/agents-md/55-git-workflow.md:6` | Duplication of a skill body | "run the ship skill (make check, verify-<app>, code-review, security review, UI checklist, Evidence, gh pr ready)" repeats the ship skill steps. The skill name alone is the pointer. |
| 4 | `ai/agents-md/55-git-workflow.md:13` | No-op / duplication | "code-review compares against the merge-base with main (git diff main...HEAD)". Matt's code-review already says "`git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base)". |
| 5 | `ai/agents-md/55-git-workflow.md:9` | Invocation rule | "Run /improve-codebase-architecture and /retro". Both are `disable-model-invocation: true`. Matt: "phrase it as an instruction for the human to act on". He runs architecture review from CI cron instead (CVM `architecture-review.yml`). |
| 6 | `ai/agents-md/40-audit-before-use.md:13` | Negation | "Never try to get around it (no other command, no other tool, no inner shell)". This lists three bypass ideas that the reader may not have had. The positive target ("tell me the command and why") comes last. |
| 7 | `ai/agents-md/40-audit-before-use.md:9` | Negation | "never "pre-existing" or "expected": no skip, no delete, no failure allowlist". Four forbidden moves come before the positive "Fix the code". |
| 8 | `ai/agents-md/20-rtk.md:4` | Sediment plus negation | "Never use --ultra-compact (removed in 1.0)". The flag no longer exists, so the line names a dead option in every session. |
| 9 | `ai/agents-md/00-owner.md:9` | Cut identity the leading word carries; exposition | "STE is the controlled language that aerospace and defense manufacturers use ... Its rules make sure that a tired reader ...". The leading word "ASD-STE100" already recruits the prior. The next line ("Write for that tired reader") is the operative part. |
| 10 | `ai/agents-md/80-tool-catalog.md:7` plus the `skills-guide` description | Duplicate pointer; one trigger per branch | The skills-guide skill is model-invoked, so its 82-word description is already loaded. That description lists 7 synonym triggers in 3 languages ("which skill for X", "how do I use wayfinder", "what does implement do", "list our skills", "what skills do we have", "cum folosesc", "какой скилл"). The AGENTS.md line repeats the same pointer. |
| 11 | `ai/agents-md/85-l0.md:2` (L0 table, 1088 words) | Context load for rare branches | Rows for seo, blog, browser, ui and their "not-enabled" twins load in every repo, also where those tools are off. The tie-break table repeats rows that the router already applies. |
| 12 | `ai/agents-md/30-code-navigation.md:9` | No-op | "Never put secrets or personal data in AGENTS.md." The secret-scan gate already blocks secrets at commit. The line restates the gate and adds a negation. |

Also: `ai/agents-md/60-characters.md:3` uses a negation first ("Never write the em dash"), but it pairs the positive at once (line 4) and a lint backs it. That is the form Matt allows: "pair it with the positive target".

## E. Our wrapping versus his original use

Hook code size: `hooklib.py` 3242 lines, `router.py` 1945, `stop-check.py` 441: **5628 lines of Python**, plus `routing.yaml` 399 lines and `hooks.json` 120 lines. Per-gate sizes below are approximate: I summed the functions whose names match each gate in `plan-research/hookfuncs.txt`.

| Our hook or gate (rule id) | Strength | What it forces | Approx. code | How Matt gets the same behaviour |
|---|---|---|---|---|
| `writing-for-agents` | gate (PreToolUse deny) | Load the skill before an edit or shell write of AGENTS.md, CLAUDE.md, CLAUDE.local.md or a SKILL.md | part of skill-proof code, about 163 lines across 13 functions | Model-invoked description "Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md." `retro` calls it with the Skill tool. No gate. |
| `ship` | gate before `gh pr ready` | Run our ship skill (check, verify, Matt code-review, security review) | shares the skill-proof code | `implement` ends with "call the Skill tool with "code-review""; `implement-spec` step 8 marks the PR ready after code-review. CVM: the ruleset needs green `check`; `agent-review.yml` runs review in CI. |
| `pr-rules` | gate before `gh pr create/edit/ready` | Mermaid, Evidence, Door, Blast Radius, author-sessions block, test file on fix PRs, verify evidence at head SHA | about 320 lines, 13 functions (`gate_pr`, `pr_*`) | `pr` skill, model-invoked, "Use when writing a PR body." No body check. CVM: PR body rule is text in `merging.md` step 4. |
| `merge-approval` | gate | Merge only after the owner's latest message says merge or approve; no push to main | about 45 lines | CVM: GitHub ruleset ("only gate"); agents use `gh pr merge --auto`; migration PRs "Matt merges" (text). |
| `worktree-first` | gate (Edit/Write on main) | Work in a worktree | about 66 lines | CVM: text ("Every code change lands through a PR from a fresh worktree") plus a runtime DB guard in worktrees. `implement-spec`: one worktree per ticket in the skill text. |
| `no-verify` | gate | No `--no-verify` | about 33 lines | CVM: text only ("Never skip hooks: no `git commit --no-verify`, no `HUSKY=0`"). CI re-runs the same checks, so a skipped hook cannot reach `main`. |
| `winner-gate` (winners table) | gate on the Skill tool | Deny OMC "loser" skills (plan, tdd, review, pr, research, wiki, release) | about 38 lines plus table | No equivalent. `.out-of-scope/harness-name-collisions.md`: use namespaced invocation (`/mattpocock-skills:code-review`). He does not install a competing skill set. |
| skill card (SessionStart) | inject | Lists must-use, hint and typed-only skills; for typed-only gives the SKILL.md path "read and follow" | `render_card` 17 lines plus `typed_skills_note` 20 | Opposite design. Typed-only means "reachable only by the human typing its name"; the human router is `ask-matt`. Our card lets the model read typed-only skills, which removes the zero-context-load trade. |
| `feature-grill` | nudge (prompt regex) | grill-with-docs, to-spec, to-tickets, implement on a feature prompt | `_ph_feature_flow` 21 lines plus a long regex | Human types `/grill-with-docs`. README: "Use them _every_ time you want to make a change." |
| `tdd` | nudge (was a stop) | Use the tdd skill on test-first prompts | stop/nudge code | Model-invoked description plus `implement` Skill call. He accepts misses (`docs/engineering/tdd.md:58`). Our log: "the baseline showed 0/3 tdd skill use"; "as a stop, 1 of 1 block was false" (`routing.yaml`). |
| `diagnosing-bugs` | nudge (was a stop) | Use the skill on bug and perf prompts | stop/nudge code | Description triggers plus in-skill completion criteria. Our log: "as a stop, 6 of 6 blocks were false" (`routing.yaml`). |
| `tracker-flow`, `domain-docs` | nudge | to-spec/to-tickets; grill-with-docs/domain-modeling | regex rows | `setup-matt-pocock-skills` writes `docs/agents/*.md` and 3 pointer lines; ADR 0001 hard-dependency pointer. |
| `verify-before-done` + Stop hook `stop-check.py` | nudge + Stop runs `check-fast` | Run checks and verify-<app> before done | `stop-check.py` 441 lines; verify code about 288 lines | `implement`: "Run typechecking regularly ... the full test suite once at the end." CVM: husky pre-commit (20 commands), CI `check`, verify-cvm skill plus a `CLAUDE.md` rule. |
| `merge-review` (SessionStart) | nudge | After a merge, run improve-codebase-architecture and retro | `merge_review_note` 36 lines | README: run improve-codebase-architecture "once every few days". CVM: weekday cron in CI. `retro` is typed-only. |
| `no-em-dash`, `ste-sentence` | nudge after write | Lint prose | about 19 lines | Skills repo: text rule only, and its files hold 0 em dashes. CVM: no rule, 30 em dashes in `CLAUDE.md`. |
| `ledger-nudge` | nudge | Keep regression-ledger tests green | about 133 lines | `diagnosing-bugs` Phase 5 and 6: regression test, "The hypothesis that turned out correct is stated in the commit / PR message". |

Summary: he forces 0 skills by hooks. We force 2 skills by gate (writing-for-agents, ship), 5 PR or git actions by gate, and nudge 7 more. Our own data says the nudges and stops were weak: "ignored 72 of 88 times" (docs-lookup), "as stops 7 of 7 blocks were false" (hooks `README.md`).

## F. Eight lessons for a generic, plug-and-play setup

1. **Gate the merge, not every tool call.** CVM has 1 agent hook (12 lines) and 1 GitHub ruleset; the ruleset "holds for agents without exception". We run 5628 lines of hook Python, and our stops were false 7 of 7 times. Ship a required CI `check` and a ruleset template as the core gate. Keep hooks for harness-level safety only. (C.2 rows 1, 20; E summary.)
2. **Turn mechanical rules into checks that every agent and human hit.** Matt: "a mechanical one ... gets a deterministic check, full stop". CVM runs 20 pre-commit commands and 19 guard scripts, and about 14 of 24 standards name their check. An agent-only hook misses Codex, humans and CI. (B lint row; C.1.)
3. **Budget the always-loaded words and lint the budget.** His rule: pointers only. Skills repo 559 words; CVM 1644 words; ours 3206 words plus the skill card and about 140 descriptions. Even CVM drifted ("the five file guards" vs 19 scripts). Add a CI word cap and a no-op pass. (C.3, D.2.)
4. **Respect the typed-only split.** Typed-only skills cost zero context because only the human fires them. Our skill card and `55-git-workflow.md:9` push the model to run them, which pays context load and breaks his contract. Use one human router (`ask-matt` or our `skills-guide`) and CI schedules (CVM architecture-review cron). (A.5, D.3 #5, E skill card.)
5. **One home per meaning; keep vendor skills unchanged and layer additions in one place.** Our PR rules live in the pr skill, `50-pull-requests.md`, the L0 row and the gate. SCOPE.md says per-user tweaks belong "in your own `CLAUDE.md` / `AGENTS.md`, or in a fork". Put our additions in the gate message or a fork, not in always-loaded prose. (D.3 #1-#4.)
6. **Put completion criteria in the artifact, then check the artifact.** His strongest steps end on a checkable artifact: "one command ... already run at least once", one file per ticket. Our best gate does the same: a verify `run.log` at the PR head SHA. Prompt-regex nudges for tdd and diagnosing-bugs did not work (0/3 tdd use, 6 of 6 and 1 of 1 false stops). (B completion rows; E tdd and diagnosing rows.)
7. **Name the human checkpoints and accept non-compliance elsewhere.** He gates with people: seams, ticket approval, hypotheses, migration merges. He says "No instruction makes an agent comply 100% of the time". Keep hard gates for irreversible or shared actions: merge, migration, secrets, production. Leave process choice to skills and review. (B "What he leaves to the human"; C.2 rows 16-19, 22.)
8. **Test the guards and prune them.** CVM tests its guards and verify scripts, and its allowlists only shrink (complexity ratchet). Matt: "A rule that fires constantly on good code is the sign to remove it." We have 21 eval cases and logs of misses. Make every gate carry a should-fire and should-not-fire test, and delete rules whose logs show they are ignored or false. (C.1 tests row; E summary.)

## Could not confirm

- Whether Matt runs CVM sessions with his skills plugin on. No `enabledPlugins` or skill copies are in the repo.
- His personal `~/.claude` settings, user-level hooks or permission rules. Nothing public shows them.
- Ruleset details beyond its name and `enforcement: active` (required reviews, bypass list). Branch protection API returned 404.
- That Claude Code keeps typed-only descriptions out of context. I took this from his `SKILL-MECHANICS.md` ("Zero context load"), not from a test in this session.
- Exact per-gate line counts. My numbers sum function sizes found by name match in `hooklib.py`, `router.py` and `stop-check.py`; shared helpers are not split.
- The CVM class table is my own classification. Some rows have a secondary class.
- Any LLM behaviour eval in either repo. I found none; the CVM tests cover scripts and guards only.
- The "roughly 140 skills" figure is a hand count of the skill list in this session, not a measured token count.
