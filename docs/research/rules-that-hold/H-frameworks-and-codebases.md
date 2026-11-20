# H: Agent-setup frameworks and agent files of famous codebases

Date of research: 2026-11-20. Method: `gh api` (repo metadata, recursive trees, raw file contents, per-file commit history) and WebFetch/WebSearch for blog posts and papers. Raw downloads are in `H-data/` next to this file. History numbers come from `hist.sh` in this folder: it lists all commits that touch one path (renames are not followed), and measures the file at the first and the last commit. "Peak" is the largest size in a sample of about 12 commits, so the real peak can be higher.

Word counts are `wc -w` of the raw file. "Always-loaded" means text that enters context in every session of a user of the framework (or of a contributor in the codebase), before any skill is invoked.

Downloaded content was read as data only. One file (zed `AGENTS.md`) contains an instruction aimed at agents (a "HARD RULE" to edit `README.md`). I did not act on it. It is described below as a design feature.

---

## Part 1: Frameworks

### 1. garrytan/gstack (142,195 stars)

Source: https://github.com/garrytan/gstack (API `repos/garrytan/gstack`).

- **What loads every session (user side):** the Claude skill listing for 76 skills (count of `*/SKILL.md` at depth 1 in the tree; total SKILL.md bytes in the repo: 2,132,382, but only the descriptions are listed). The README tells the user to add a short "gstack" section to `CLAUDE.md` (one rule: use `/browse`, never the Chrome MCP tools) and says the section "needs no skill list" (`README.md` lines 38 and 309). A `UserPromptSubmit` hook adds at most one routing line per prompt. Size of the listing: not measured.
- **Contributor side:** `CLAUDE.md` 631 lines / 4,832 words, `AGENTS.md` 275 lines / 2,626 words.
- **Hooks:** `hosts/claude/hooks/` holds about 10 hook entry points in TypeScript, 2,982 lines in total for the `.ts` files I fetched. `docs/install.md` lists the registered ones:
  - `PreToolUse` (Bash, PowerShell) `destructive-guard-hook`: runs `careful/bin/check-careful.sh`. It returns `ask` for destructive families and `deny` for two catastrophic shapes. In headless sessions an `ask` becomes a `systemMessage` warning. "Always exits 0." A deny reason "which the model reads" does not name the off switch (file header).
  - `Stop` `skill-contract-stop-hook`: "blocks once when a contract skill ends without its required outputs". It fails open on every error, writes a state record before it blocks, and logs every decision to one line in a log file (file header).
  - `UserPromptSubmit` `skill-route-hook`: deterministic match of the prompt against installed skill triggers. "Always exits 0 and never exits 2: it can never block a prompt." Internal deadline 1,500 ms under a 5 s timeout.
  - `Stop`/`SubagentStop` `ceo-review-gate`, `autoplan-stop-gate`; `Stop` `timeline-stop-hook`; `AskUserQuestion` `PreToolUse`/`PostToolUse` preference hooks (setup asks before it registers these); `SessionStart` auto-update in team mode.
  - Team mode: a `required` hook in the project `.claude/` blocks skills when gstack is missing (`docs/install.md` line 25).
- **Permissions/sandbox shipped:** not verified.
- **Sequencing:** `/office-hours` then `/autoplan` (CEO, design, eng reviews) then build, `/review`, `/qa`, `/ship`, `/land-and-deploy`. Gates are Stop hooks (`autoplan-stop-gate`, `ceo-review-gate`) and skill "contracts" (required outputs).
- **Verification:** `/review`, `/qa` (real browser), outside review through the Codex CLI (`README.md` host table).
- **Self-tests:** 1,554 `test/*.test.ts` files; 35 workflows that include `evals.yml`, `evals-periodic.yml`, `evals-marathon.yml`, `eval-sweep.yml`, `skill-docs.yml`, `quality-gate.yml`. A "size ledger" test caps SKILL.md bytes across a merge train (`test/size-ledger.test.ts`, baseline `skillMdBytes: 187_706`).
- **Install/update:** `git clone ... ~/.claude/skills/gstack && ./setup`; registers hooks in `~/.claude/settings.json`; `SessionStart` auto-update "throttled to once/hour"; `stable` and `main` channels (`README.md` lines 38-50). Supports 10+ hosts (`hosts/*.ts`).
- **History of `CLAUDE.md`:** 121 commits. First 2026-03-12: 38 lines / 187 words. Sampled peak 9,095 words (2026-08-17). Now 631 lines / 4,832 words. It shrank by about 47% after commit `394db326` "token-load reduction: preamble runtime scripts, gated onboarding, 20 skill carves, CLAUDE.md trim (#2691)" (2026-08-27) and `7204a39a` "diet skills" (2026-10-28). `AGENTS.md`: 46 commits, 411 words to a peak of 3,586 words (2026-10-31), now 2,626.
- **Copy:** the Stop-hook "contract": block once when a required output is missing, fail open, one log line per decision.
- **Avoid:** the scale (3,017 files under `test/`, 35 workflows, 10 hosts). One owner cannot keep it green.

### 2. EveryInc/compound-engineering-plugin (26,168 stars)

Source: https://github.com/EveryInc/compound-engineering-plugin.

- **What loads every session:** the listing for 39 skills (46 SKILL.md files, 7 are test fixtures). The 42 reviewer and researcher "agents" are no longer plugin agents: they live as prompt files under `skills/*/references/agents/` and load only inside a skill. `README.md` line 74: "Specialist reviewer and research behavior lives inside the skills as local prompt assets."
- **Contributor side:** `AGENTS.md` 286 lines / 5,732 words; `CLAUDE.md` is a 9-byte symlink to it.
- **Hooks:** none shipped. The only `hooks.json` files are test fixtures (`tests/fixtures/*/hooks/hooks.json`).
- **Permissions:** none shipped. The eval harness uses `--read-only` (Codex `--sandbox read-only`; Claude `--allowedTools Read,Glob,Grep` plus a `--disallowedTools` list) (`tests/skill-eval-cell/README.md`).
- **Sequencing:** `ce-brainstorm` then `ce-plan` then `ce-work` then `ce-code-review` then `ce-compound` (writes `docs/solutions/`). Gate in text: `skills/ce-work/SKILL.md` line 56: "Code review must actually happen before shipping. The run is not done ... until the shipping reference has recorded either an actual completed `ce-code-review` receipt or one of its exact authorized skip states."
- **Verification:** review personas inside `ce-code-review`; CI `ci.yml` runs `release:validate`, `plugin:validate --strict`, `typecheck`, `bun test` (`AGENTS.md` "CI and Quality Gates").
- **Self-tests:** `tests/skill-eval-cell/` (an eval "cell"): it extracts a skill from a git ref and runs the same prompt on `claude`, `codex` and `grok`. It isolates the operator setup: Claude runs with `--setting-sources project,local` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`; Codex runs on a private `CODEX_HOME`. Packs freeze criteria and grader hashes. Policy: deterministic invariants go to `bun test`; prose behavior goes to fresh-agent evals, "not a CI job" (`AGENTS.md` table "What belongs where").
- **Rule about guards (`AGENTS.md` "Right-size new mechanical guards"):** "Prefer tightening an existing guard over adding a new suite"; "Pin the smallest falsifiable unit"; "If the failure needs an LLM to judge, keep it as a behavioral eval; do not fake it as a brittle string test."
- **Install/update:** `/plugin marketplace add EveryInc/compound-engineering-plugin` then `/plugin install compound-engineering`; manifests for Codex, Cursor, Devin, Grok, Kimi, Antigravity. Update: refresh the marketplace, then `/plugin update` (`README.md` lines 28-33).
- **History of `AGENTS.md`:** 98 commits. First 2026-01-22: 48 lines / 311 words. Sampled peak 8,158 words (2026-09-09). Now 5,732 words. Shrink commits: `26f38961` "ce-compound: 90% smaller SKILL.md, references carry the phases (#1477)", `e36ddb8c` "slim the always-loaded body (#1357)", `142dbabc` "move review criteria into CODING_STANDARDS.md files (#1839)".
- **Copy:** the eval cell with operator isolation, and the "what belongs where" split (CI for deterministic, evals for prose).
- **Avoid:** a 5,700-word contributor AGENTS.md.

### 3. github/spec-kit (150,784 stars)

Source: https://github.com/github/spec-kit.

- **What loads every session:** nothing large. The user runs commands from 9 templates in `templates/commands/` (constitution, specify, clarify, plan, tasks, analyze, checklist, converge, implement). Each command reads `.specify/memory/constitution.md` when it needs it (template 2,346 bytes).
- **Contributor side:** `AGENTS.md` 76 lines / 464 words.
- **Hooks:** no Claude or Codex hooks. It has its own "extension hooks" (`.specify/extensions.yml`, keys `before_implement` and others) that the agent must run because the command text tells it to. The template admits the weakness: "Emitting the block alone does not run the hook" (`templates/commands/implement.md` line 49).
- **Sequencing and gates (mechanical):** `scripts/bash/check-prerequisites.sh` prints `ERROR: plan.md not found in $FEATURE_DIR` and exits 1, and has `--require-spec` / `--require-tasks`. So `/tasks` cannot start without `plan.md`, and `/implement` cannot start without `tasks.md`. Checklists are a "read-only gate": unchecked items cause "STOP and ask" (`implement.md` lines 56-81).
- **Verification:** `/analyze` (cross-artifact consistency) and checklists. No review agent.
- **Self-tests:** `uv run pytest -n auto` (`.github/workflows/test.yml`), 230 files under `tests/specify_cli`. No LLM eval paths in the tree (0 matches for "eval").
- **Install/update:** `uv tool install specify-cli`, then `specify init <project> --integration <agent>`; copies files into the project. Upgrade guide at https://github.github.io/spec-kit/upgrade.html (`README.md` lines 80-95).
- **History of `AGENTS.md`:** 76 commits. First 2025-09-20: 229 lines / 974 words. Sampled peak 4,022 words (2026-09-01). Now 464 words (-88% from peak). Commits: `6af2e64e` "Rewrite AGENTS.md for integration architecture (#2119)", `50da3a0f` "Extract agent context updates into bundled agent-context extension (#2546)".
- **Copy:** phase gates as a script that exits 1 when the previous phase's file is missing.
- **Avoid:** "hooks" that are only prose for the agent to run.

### 4. bmad-code-org/BMAD-METHOD (55,575 stars)

Source: https://github.com/bmad-code-org/BMAD-METHOD.

- **What loads every session:** v7 (alpha) installs skills with `npx skills add bmad-code-org/BMAD-METHOD/skills/<module> --skill '*'` (`README.md` lines 34-50). 36 SKILL.md files in the repo. Size of the listing: not measured.
- **Contributor side:** `AGENTS.md` 35 lines / 337 words, inside a managed block `<!-- bmad:context -->` with the stamp "Verified 2026-10-04 against 3cae711e. Managed by bmad-project-context; edits inside this block are replaced on refresh."
- **Hooks / permissions:** none found in the tree (0 hook paths).
- **Sequencing:** skills per role (analyst, PM, PO, architecture, build, code-review, retrospective). Gate detail: not verified (`tools/ticket-tree-rules.md` not read).
- **Verification / CI:** `quality.yaml` runs `pre-commit run --all-files`, `npm run lint`, `format:check`, `build`, `npm test`; `uv run tools/validate_skills.py --strict`; `coderabbit-review.yaml`.
- **Self-tests:** `skills/toolsmith/bmad-eval` (trigger evals in `evals/triggers.json`, `run_evals.py`, `run_triggers.py`, with unit tests for the harness).
- **Notable rules (`AGENTS.md`):** "Length and ambiguity are paid on every run; a corner case is paid only when it occurs." "Prefer deleting an instruction to hedging it." "Do not write automated tests for LLM output or for static source text."
- **History of `AGENTS.md`:** 12 commits, 9 lines / 46 words (2026-03-14) to 337 words now.
- **Copy:** the "verified against <sha>" stamp in a managed block, and "prefer deleting to hedging".
- **Avoid:** many role personas for a one-person workflow (judgement, not measured).

### 5. steveyegge/beads, now gastownhall/beads (28,864 stars), and gastownhall/gastown (18,851 stars)

`gh api repos/steveyegge/beads` resolves to `gastownhall/beads`. Gas Town is public at `gastownhall/gastown`: "Multi-agent orchestration system ... persists work state in git-backed hooks" (`README.md`).

- **What loads every session:** the output of `bd prime` through a `SessionStart` hook and again on `PreCompact` (`plugins/beads/.claude-plugin/plugin.json`). For Codex: `SessionStart`, `PreCompact`, `PostCompact`, `UserPromptSubmit` call `bd codex-hook ...` (`plugins/beads/.codex-plugin/hooks/hooks.json`). `bd init` also writes a short AGENTS.md section. Size of `bd prime` output: not verified (I did not run it).
- **Design decision:** `plugins/beads/skills/beads/adr/0001-bd-prime-as-source-of-truth.md`: SKILL.md "Reduced from 3,306 to ~500 words"; CLI reference comes from `bd prime` and `bd --help`, so "No version drift possible".
- **Hooks in the repo (contributor side):** `.claude/settings.json` registers two `PreToolUse` Bash hooks. `block-interactive-cmds.sh` denies `cp`/`mv`/`rm` without `-f` and returns a fix-it reason: "BLOCKED: `cp` without `-f` flag may hang on interactive prompts ... Use `cp -f ...` instead, or prefix with `command cp`". `block-gh-watch.sh` (not read).
- **Sequencing:** a dependency graph of issues; agents take work from `bd ready` (unblocked items). "Async gates" are documented in skill resources (not read).
- **Self-tests:** Go tests (5,779 files in the tree; 20 test-dir paths by my regex). LLM evals: none found.
- **Install/update:** `brew install beads` or the install script; `bd setup claude|codex|cursor|...` writes hooks and settings (`README.md` lines 30-47).
- **History of `AGENTS.md`:** 125 commits. First 2025-10-15: 326 lines / 1,528 words. Sampled peak 6,112 words (2025-11-07). Now 1,892 words. Commits: `21a0656a` "Extract detailed instructions to prevent context pollution" (2025-11-21), `a930fa35` "condense event-driven daemon section", `0e017821` "move internal/maintainer docs from docs/ to engdocs/".
- **Copy:** let the tool print its own context (`prime`) instead of copying docs; re-inject after compaction; deny reasons that say the exact fix.
- **Avoid:** a full issue database for a one-person setup (judgement).

### 6. wshobson/agents (42,731 stars), chosen over SuperClaude-Org/SuperClaude_Framework (23,950 stars)

SuperClaude in one line: `CLAUDE.md` 10 commits, 445 to 1,476 words (2025-10-18 to 2026-03-22), 42 agent files, 61 command files, no test paths in the tree, last push 2026-09-27.

wshobson/agents (https://github.com/wshobson/agents):

- **Size:** 93 plugins (91 local), 199 agents, 185 skills, 103 commands (`AGENTS.md` first paragraph). Users install single plugins, so a session loads only the enabled plugins.
- **Contributor side:** `AGENTS.md` 84 lines / 804 words; `CLAUDE.md` is a symlink. It says: "This file should never grow beyond ~150 lines (per OpenAI's harness-engineering practice)" and "this file is a **map**, not an encyclopedia".
- **Hooks:** only in two governance plugins (`plugins/protect-mcp/hooks/`, `plugins/review-agent-governance/hooks/`: `evaluate.sh`, `sign.sh`) and a `block-no-verify` skill. No repo-wide hook.
- **Verification / CI:** `validate.yml` runs `make validate STRICT=1`, `make garden` (`tools/doc_gardener.py`: "dead links, stale artifacts, oversize skills"), `make test`, `make smoke-test` (real CLIs). Also `claude-code-review.yml` and `eval-report.yml`. "CI fails on drift" between source and generated per-harness files.
- **Self-tests:** `tools/tests/` (13 test files, for example `test_round_trip.py`, `test_validate_generated.py`), plugin-eval "three-layer quality evaluation framework" (`docs/plugin-eval.md`, not read).
- **Install:** Claude marketplace; generators for Codex, Cursor, OpenCode, Antigravity, Copilot, Pi (`make generate HARNESS=...`).
- **History of `AGENTS.md`:** 38 commits, 74 lines / 565 words (2026-05-22) to 84 lines / 804 words. Stable size.
- **Copy:** one source, generated per agent, CI fails on drift; a doc gardener; an explicit size cap in the file.
- **Avoid:** a catalog of hundreds of agents and skills.

### 7. getsentry/skills (1,188 stars) and getsentry/sentry (45,802 stars)

**getsentry/skills** (https://github.com/getsentry/skills):

- 31 skills, 2 agents (`agents/code-simplifier.md`, `agents/senpai.md`).
- `AGENTS.md` 38 lines / 245 words. History: 21 commits, 389 words (2026-01-05) to 245 words now (shrank).
- `.claude/settings.json`: a permission allow list of read-only Bash (`ls`, `git status`, `gh pr view`, ...), 7 `WebFetch(domain:...)` entries, and 31 `Skill(sentry-skills:...)` entries. `deny: []`.
- `warden.toml`: Warden runs the `skill-scanner` skill on every PR to `**/skills/**`, `failOn = "high"`.
- Evals: AXIS (`npx @netlify/axis run --config skills/pr-writer/evals/axis.config.json`) with JSON scenarios for `pr-writer` and `skill-writer`.
- `skills/agents-md/SKILL.md`: "Target under 60 lines; never exceed 100." "Do not restate linter, formatter, or typechecker config." "Do not list installed skills or plugins." "symlink `CLAUDE.md` to `AGENTS.md`".

**getsentry/sentry** (https://github.com/getsentry/sentry):

- Root `AGENTS.md` 134 lines / 930 words. Nested: `src/AGENTS.md` (1,683 words), `static/AGENTS.md` (1,336), `tests/AGENTS.md` (678), plus 3 deeper files. Each `CLAUDE.md` is an 11-byte pointer.
- 31 skills in `.agents/skills/`; `.claude/skills` is a symlink to it. 3 Claude commands.
- `.claude/settings.json`: MCP settings only. No hooks, no permissions.
- Content: commands (venv, `prek`, pytest by file), a routing list to the nested files, a customer-data prohibition, PR split rule ("A CI check enforces this"; the exact workflow: not verified).
- CI that enforces conventions: `pre-commit.yml` (prek), lint suppression budgets (`pnpm run lint:suppressions --ci`), `migrations-drift.yml`, `type-coverage-diff.yml`, `codeowners-coverage.yml`, `openapi-diff.yml`.
- **History of root `AGENTS.md`:** 44 commits. First 2025-10-30: 665 lines / 2,367 words. Sampled peak 3,040 words (2025-11-10). Now 930 words (-69%). Commits: `c9b951f2` "Trim noise from root and tests AGENTS.md (#116875)", `8bc252d2` "Trim derivable content from AGENTS.md (#121311)", `774aeab7` "compact AGENTS.md files and defer deep guides to skills (#121469)", `259ca731` "Move backend guidance into src (#124775)", `bb679e87` "Move frontend tooling details out of root AGENTS.md (#127826)". Earlier `35c43032` "Remove Cursor specific rules (#111004)".
- **Copy:** the trim sequence (derivable content out, deep guides to skills, area rules to nested files) and the read-only allow list.
- **Avoid:** nothing large; the setup is lean.

---

## Part 2: Famous codebases

| Repo | Stars | Main file | Lines / words | Commits, first size, now | Nested / scoped files | Hooks / settings |
|---|---|---|---|---|---|---|
| vercel/next.js | 143,626 | `AGENTS.md` | 587 / 4,859 | 49; 1,019 w (2026-01-05); 4,859 w (grew) | 6 nested `AGENTS.md` + `.github/AGENTS.md` (441 w); 21 skills in `.agents/skills`; `.claude/skills` symlink; `.cursor/commands` | none found |
| ghostty-org/ghostty | 64,273 | `AGENTS.md` + `AI_POLICY.md` | 40 / 225; 65 / 508 | 18; 88 w (2025-09-03); 225 w | 9 nested `AGENTS.md`; 1 skill; 1 command | none |
| zed-industries/zed | 95,405 | `AGENTS.md` (was `.rules`) | 190 / 1,888 | `.rules`: 23; 1,107 w (2025-04-17); renamed to `AGENTS.md` 2026-11-16 (#66716) | `docs/AGENTS.md` (17,810 bytes); 4 skills | none |
| astral-sh/ruff | 51,325 | `AGENTS.md` | 240 / 2,914 | 46; 675 w (2026-03-07); 2,914 w (grew) | `.agents/` local plugin marketplace, 7 skills, threat models | `SessionStart` hook (env setup) |
| astral-sh/uv | 92,450 | `AGENTS.md` | 49 / 551 | 9; 212 w (2026-04-07); 551 w | 1 Codex skill | none |
| microsoft/vscode | 195,703 | `.github/copilot-instructions.md` (`AGENTS.md` is a 50-word pointer) | 178 / 2,173 | 47; 1,757 w (2024-11-28); 2,173 w | 36 `*.instructions.md` with `applyTo` globs; 54 skills; nested `AGENTS.md` incl. one of 275,332 bytes (`src/vs/platform/agentHost/AGENTS.md`) | `.github/hooks/cloud-sandbox.json` (`sessionStart`) |
| PostHog/posthog (choice) | 40,987 | `AGENTS.md` | 259 / 3,835 | 198; 354 w (2025-09-23); peak 6,387 w (2026-10-19); 3,835 w | about 27 nested `AGENTS.md`; 15 `.claude/rules/*.md` with `paths:`; 11 agents; 121+ skills (tree truncated) | `SessionStart` setup hooks |
| n8n-io/n8n (choice) | 211,516 | `AGENTS.md` | 481 / 3,519 | 60; 915 w (2025-11-25); 3,519 w (grew) | about 44 `AGENTS.md`/`CLAUDE.md`; 31 skills; local plugin (2 agents, 2 commands) | allow list; async `PostToolUse` telemetry on `Skill` |

Details per repo:

- **next.js:** content is commands (build, fast dev loop, tests), test-writing rules, PR format, secrets rules, "Context-Efficient Workflows", anti-patterns. Prohibitions: "Do NOT add 'Generated with Claude Code' or co-author footers", "Do NOT mark PRs as ready". The root `CLAUDE.md` was deleted (last commit 2026-09-22); Claude Code v2.1.277+ reads `AGENTS.md` when no `CLAUDE.md` exists (https://code.claude.com/docs/en/memory, section "AGENTS.md"). Enforcement: lint-staged pre-commit (prettier, eslint; `AGENTS.md` "Commit and PR Style"), `build_and_test.yml`, and `next-upgrade-evals.yml` (agent evals of the upgrade flow).
- **ghostty:** `AGENTS.md` is commands plus one prohibition: "Never create an issue. Never create a PR." with a joke file as the response. `AI_POLICY.md` requires disclosure and "Bad AI drivers will be denounced". Enforcement is social and CI: `vouch-check-pr.yml` uses `mitchellh/vouch/action/check-pr` v1.5.0 with `auto-close: true` (unvouched contributors' PRs close). `test.yml` has a `required` job that needs `prettier`, `swiftlint`, `alejandra`, `typos`, `shellcheck`, and `zig fmt --check .`.
- **zed:** Rust and GPUI traps, PR hygiene, crash workflow, and "Rules Hygiene": new rules must be "Non-obvious", "Repeatedly encountered", "Specific enough to act on"; "Rules should be **traps to avoid**, not **maps to follow**"; agents propose "Suggested AGENTS.md additions" in the PR body and must not edit `AGENTS.md` during feature work. The file also has a "HARD RULE" that makes an agent put a review banner in `README.md` that only the human may remove: a human-review tripwire. Enforcement: `danger.yml` with `script/danger/dangerfile.ts` calls `fail("This PR is missing release notes.")` and shows the exact format, including the `[GPUI]` entry.
- **ruff:** sections: PR conventions, "Code Review Rules" (nitpicky, numbered, severity order, threat models), "Writing for human readers", test commands, mdtests, clippy, ty internals. `.claude/settings.json` enables the local `ty-skills` plugin and a `SessionStart` hook that installs `gh`, clippy, rustfmt on Claude Code web and prints "nextest is not installed, so just use 'cargo test' instead." Enforcement: CI clippy and tests (workflow details not verified).
- **uv:** 36 bullets in ALWAYS / NEVER / PREFER / AVOID form, mostly Rust and test style. Examples: "NEVER assume clippy warnings or test failures are pre-existing", "NEVER suppress the `dangerous-triggers` security lint", "DO NOT leak our conversation ... into code comments, pull request descriptions". Enforcement: clippy and the CI lint the file names (not verified line by line).
- **vscode:** project overview, validation steps, coding guidelines, "Public Content" (no internal data), and a "Learnings" section that grows when the user says "learn!" (`.github/instructions/learnings.instructions.md`). Path scoping: `applyTo: src/vs/**` frontmatter in instruction files. Enforcement: a local ESLint plugin (`.eslint-plugin-local/`, with its own `AGENTS.md`) and hygiene checks (copyright header, localization) (rule-level mapping not verified).
- **PostHog:** root file routes to topic guides (`.agents/architecture.md`, `.agents/code-style.md`, ...) and has a "Mandatory skill invocation" list. Key mechanism: each rule in the topic guides carries `[lint: <id>]` or `[review]`. `posthog/test/repo_invariants/test_agents_md_enforcement_tags.py` (6,179 bytes) "fails the build on an untagged rule, and on a `[lint: …]` that names a rule, code, or file which no longer enforces anything" (`.agents/skills/editing-agents-md/SKILL.md` section 4). Counts: `code-style.md` 3 lint / 20 review tags; `architecture.md` 9 lint / 22 review tags. Rule ladder: linter, then pre-commit, then skill, then AGENTS.md ("Rung 4 is the last resort"). Semgrep rules put "the migration playbook in the rule's `message:` field". `posthog/test/repo_invariants/` has about 60 invariant tests with ratchet baselines. History: shrink commit "move topic rules out of the root agents file (#127194)" (2026-11-04), 6,387 to 3,835 words.
- **n8n:** project overview, guidelines, commands, architecture, TypeScript and persistence boundaries, ESLint layers. Settings: permission allow list (`pnpm lint:*`, `pnpm test:*`, `Edit(.claude/plans/*)`), a local plugin, and an async `PostToolUse` hook on `Skill` that sends anonymized skill-usage telemetry. No gate hook.

---

## Part 3: Published evidence

| Source | Method | Measured numbers |
|---|---|---|
| Vercel, "AGENTS.md outperforms skills in our agent evals", Jude Gao, 2026-01-27 (https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) | Hardened eval suite on Next.js 16 APIs that are mostly absent from training data; same tests for each configuration, with retries. Case count and models: not stated. | Pass rate: baseline 53%; skill (default) 53%; skill with explicit instruction 79%; `AGENTS.md` docs index 100%. Skill never invoked in 56% of cases by default; trigger rate 95%+ with explicit instruction. Index compressed from about 40 KB to 8 KB (-80%) with 100% kept. Wording of the skill instruction changed behavior ("You MUST invoke" vs "Explore project first, then invoke"). |
| OpenAI, "Harness engineering: leveraging Codex in an agent-first world", Ryan Lopopolo, Feb 2026 (https://openai.com/index/harness-engineering/) | Experience report. Direct fetch returned HTTP 403; content from search summary and mirrors (https://github.com/celesteanders/harness/blob/main/docs/research/260211_openai_harness_engineering_codex.md, https://alexlavaee.me/blog/openai-agent-first-codebase-learnings/). | "we treat it as the table of contents"; AGENTS.md about 100 lines; docs tree (`docs/design-docs/`, `docs/product-specs/`, `docs/exec-plans/`, `docs/references/`) is the system of record; a single huge AGENTS.md failed. Custom lints and structural tests enforce layers (Types, Config, Repo, Service, Runtime, UI), structured logging, naming, file size limits. "we write the error messages to inject remediation instructions into agent context." Secondary report: about 1M lines over 5 months, 3 engineers, 3.5 PRs per engineer per day (not verified). |
| Gloaguen et al., ETH Zurich / LogicStar, "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?", arXiv 2602.11988 (v1 2026-02-12, v3 2026-09-29) (https://arxiv.org/html/2602.11988) | SWE-bench Lite (300 tasks, 11 repos) with LLM-generated files; new CTXbench (138 instances, 12 repos, from 5,694 PRs) with developer files. Claude Code + Sonnet-4.5, Codex + GPT-5.2 and GPT-5.1 mini, Qwen Code + Qwen3-30B-coder. | LLM-generated files: success -0.5% (SWE-bench) and -2% (CTXbench), not significant; cost +20% and +23%; steps +2.45 and +3.92. Developer files: success +2.4% (p = 21%), steps +3.34, cost up to +19%. Instructions are followed: `uv` used 1.6 times per instance when mentioned vs under 0.01 when not; repo tools 2.5 vs under 0.05. Overviews did not help agents find files. |
| Lulla et al., "On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents", arXiv 2601.20404 (https://arxiv.org/abs/2601.20404) | 10 repos, 124 PRs, agents with and without AGENTS.md. | Median runtime -28.64%; output tokens -16.58%; completion "comparable". |
| McMillan, "Instruction Adherence in Coding Agent Configuration Files: A Factorial Study of Four File-Structure Variables", arXiv 2605.10039 (2026-05-11) (https://arxiv.org/abs/2605.10039) | 1,650 Claude Code sessions, 16,050 function-level observations, 2 TypeScript codebases, 5 tasks, Sonnet 4.6 (Opus 4.6 check); target: one trivial annotation rule. | No detectable effect of file size (Bayes factor BF10 0.05-0.10 supports the null), position, architecture, or contradictions in adjacent files (BF10 0.05-0.10). Largest effect: each additional generated function in a session gave about 5.6% lower odds of compliance (OR 0.944), post hoc, replicated. Number of instructions was not a variable. |
| dos Santos et al., "Configuration Smells in AGENTS.md Files", arXiv 2606.15828, SCAM 2026 (https://arxiv.org/abs/2606.15828) | Grey literature review plus mining of 100 popular repos with AGENTS.md or CLAUDE.md. | Lint Leakage 62%, Context Bloat 42%, Skill Leakage 35%. PostHog's skill cites Conflicting Instructions 28%, Init Fossilization 24%, Blind References 16% (from `editing-agents-md/SKILL.md`; not on the abstract page, so not verified). |
| Jaroslawicz et al. (Distyl AI), "How Many Instructions Can LLMs Follow at Once?" (IFScale), arXiv 2507.11538 (https://huggingface.co/papers/2507.11538) | 500 keyword-inclusion instructions in a report task, density 10 to 500, 20 models from 7 providers. | Best frontier model 68% accuracy at 500 instructions; three degradation patterns; bias toward earlier instructions. |
| Anthropic, "Introducing advanced tool use" (https://www.anthropic.com/engineering/advanced-tool-use) | Internal MCP evals. | 58 tools from 5 servers = about 55K tokens before work; seen up to 134K. Tool Search: Opus 4 49% to 74%, Opus 4.5 79.5% to 88.1%; about 85% fewer tokens. Use deferred loading at 10+ tools or over 10K tokens of definitions; keep the 3-5 most-used tools loaded. |
| Claude Code docs, memory and skills (https://code.claude.com/docs/en/memory, https://code.claude.com/docs/en/skills) | Vendor guidance. | "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence." CLAUDE.md is "context, not enforced configuration. To block an action ... use a PreToolUse hook". Skill listing budget = 1% of the context window (`skillListingBudgetFraction`), per-skill description cap 1,536 characters; least-used descriptions drop first. SKILL.md under 500 lines. After compaction: first 5,000 tokens per skill, 25,000-token combined budget. "Claude skipped a rule that must hold every time: move the rule into a hook." |
| Codex docs (from sibling note `D-codex.md` lines 38 and 324) | Vendor docs and source. | `project_doc_max_bytes` default 32 KiB (over budget: truncated, later files skipped). Skill metadata budget 2% of context or 8,000 characters. |

---

## Synthesis

### Table of all entries

"Always-loaded words" = main instruction file that loads in each session in that repo (for frameworks: the contributor file; the user-side load is mostly a skill listing, see notes). "Hook cmds" = agent hook commands that the repo or framework registers. "Self-tests" = tests or evals of the agent setup itself (not of the product).

| Entry | Stars | Always-loaded words | Hook cmds | Skills / commands / agents | Main enforcement layer | Self-tests |
|---|---|---|---|---|---|---|
| gstack | 142,195 | 4,832 (contrib); user: 76-skill listing + 1 rule | about 10 (PreToolUse deny/ask, Stop gates, prompt routing) | 76 skills | Agent hooks + CI evals | yes (evals, size ledger) |
| compound-engineering | 26,168 | 5,732 (contrib); user: 39-skill listing | 0 | 39 skills, 42 persona prompts in skills | CI validators + text gates in skills | yes (eval cell, 3 CLIs) |
| spec-kit | 150,784 | 464 (contrib); user: none until a command | 0 (prose "extension hooks") | 9 commands | Scripts that exit 1 on missing files | unit only (pytest) |
| BMAD | 55,575 | 337 | 0 | 36 skills | pre-commit + skill validator + CodeRabbit | yes (bmad-eval triggers) |
| beads | 28,864 | 1,892 (contrib); user: `bd prime` output | 2 plugin (SessionStart, PreCompact) + 2 repo deny | 3 skills, 30 commands | Generated context + deny hooks | unit only |
| wshobson/agents | 42,731 | 804 | 0 repo-wide (2 governance plugins) | 185 skills, 103 commands, 199 agents | CI validate + doc gardener | yes (smoke, plugin-eval) |
| getsentry/skills | 1,188 | 245 | 0 | 31 skills, 2 agents | Permission allow list + Warden on PR | yes (AXIS evals) |
| getsentry/sentry | 45,802 | 930 (+ nested 678-1,683) | 0 | 31 skills, 3 commands | CI (prek, suppression budgets) | no |
| next.js | 143,626 | 4,859 | 0 | 21 skills | lint-staged + CI | yes (upgrade evals) |
| ghostty | 64,273 | 225 (+ policy 508) | 0 | 1 skill, 1 command | CI required job + vouch auto-close | no |
| zed | 95,405 | 1,888 | 0 | 4 skills | Danger PR check + CI | no |
| ruff | 51,325 | 2,914 | 1 (SessionStart setup) | 7 skills | CI | no |
| uv | 92,450 | 551 | 0 | 1 skill | CI (clippy, lints) | no |
| vscode | 195,703 | 2,173 (+ path-scoped) | 1 (sessionStart) | 54 skills | Local ESLint plugin + CI | no |
| PostHog | 40,987 | 3,835 | 3 (SessionStart setup) | 121+ skills, 11 agents | Semgrep/invariant tests + tag test | yes (tag-enforcement test) |
| n8n | 211,516 | 3,519 | 1 (telemetry) | 31 skills, 2 agents, 2 commands | Allow list + CI | no |

### Mechanisms ranked by how many of the 16 entries use them

| Rank | Mechanism | Entries (count) |
|---|---|---|
| 1 | CI required checks | all 16 (16) |
| 2 | Text only for agent behavior (no agent-specific enforcement beyond generic CI) | ghostty, uv, zed, next.js, n8n, sentry, ruff, vscode, CE, spec-kit (10) |
| 3 | Lint or check with a fix-it message tied to an agent rule | PostHog (semgrep `message:`, tag test), zed (Danger fail with format), beads (deny reason), gstack (size ledger), CE (`bun test` contracts), wshobson (validate, garden), BMAD (`validate_skills.py`), vscode (local ESLint) (8) |
| 4 | Review subagents or AI review in CI | gstack, CE, wshobson, PostHog, getsentry/skills (Warden), BMAD (CodeRabbit), ruff (review rules) (7) |
| 5 | Agent hooks of any kind | gstack, beads, wshobson (plugins), ruff, vscode, PostHog, n8n (7); of these, hooks that deny or block: gstack, beads, wshobson governance plugins (3) |
| 6 | Git hooks (pre-commit, pre-push) | sentry (prek), next.js (lint-staged), BMAD (pre-commit), PostHog (lint-staged), CE (local pre-push) (5) |
| 7 | Permission or sandbox settings shipped | getsentry/skills, n8n (allow lists), CE eval cell (read-only sandbox) (3) |
| 8 | Phase gates by required files | spec-kit (script exit 1), gstack (Stop contract) (2 mechanical); CE review receipt (1 textual) |

### What the large frameworks did later (git history)

Seven of the main files shrank after a peak:

| File | Peak (sampled) | Now | Change | Evidence |
|---|---|---|---|---|
| spec-kit `AGENTS.md` | 4,022 w (2026-09-01) | 464 w | -88% | #2119 rewrite, #2546 extract to extension |
| sentry `AGENTS.md` | 3,040 w (2025-11-10) | 930 w | -69% | #121311 trim derivable, #121469 defer to skills, #124775 / #127826 move to nested |
| beads `AGENTS.md` | 6,112 w (2025-11-07) | 1,892 w | -69% | `21a0656a` "prevent context pollution"; ADR-0001 SKILL.md 3,306 to about 500 w |
| gstack `CLAUDE.md` | 9,095 w (2026-08-17) | 4,832 w | -47% | #2691 "token-load reduction ... CLAUDE.md trim" |
| PostHog `AGENTS.md` | 6,387 w (2026-10-19) | 3,835 w | -40% | #127194 "move topic rules out of the root agents file" |
| CE `AGENTS.md` | 8,158 w (2026-09-09) | 5,732 w | -30% | #1477 "90% smaller SKILL.md", #1357 "slim the always-loaded body", #1839 criteria to CODING_STANDARDS.md |
| getsentry/skills `AGENTS.md` | 294 w | 245 w | -17% | small trims |

Files that only grew: next.js (1,019 to 4,859 w), ruff (675 to 2,914 w), n8n (915 to 3,519 w), zed (1,107 to 1,888 w), uv (212 to 551 w), vscode (1,757 to 2,173 w).

Pattern: the shrink always moved text to one of four places: nested or path-scoped files (sentry, PostHog), skills or skill references (sentry, CE, beads), tool output (beads `bd prime`), or mechanical checks (PostHog tags and semgrep; CE `bun test` contracts). None of them deleted a rule that a check enforced; they deleted the prose copy.

### Applicability to the target setup

Target: one owner, Claude Code and Codex; 3,200-word always-loaded file with 83 instructions; 38 rules in a table, 27 reminder texts injected by a hook, measured 75% not followed; a 5,600-line Python hook router with 11 command gates; a generated project layer.

Twelve recommendations, ranked by expected effect:

1. **Delete the 27 injected reminder texts. Keep a rule only if a check backs it.** A reminder that is ignored 75% of the time costs tokens in every turn and buys little. Evidence: Vercel (skill never invoked in 56% of cases without explicit wording), arXiv 2602.11988 (context costs +20% to +23% for no reliable gain). Cost: cheap (hours).
2. **Turn each "must hold every time" rule into a `PreToolUse` deny with a fix-it reason, or into a git hook.** Claude docs: CLAUDE.md is "not enforced configuration ... use a PreToolUse hook". Model the reason text on beads `block-interactive-cmds.sh` ("Use `cp -f ...` instead"). Cost: medium (days).
3. **Cut the always-loaded file to a map of about 100 lines (under 1,000 words).** Keep only what no tool can carry: the reply shape, the writing style, the few prohibitions with no check. Sources: OpenAI harness engineering (about 100-line table of contents), wshobson cap (150 lines), getsentry `agents-md` (60 to 100 lines), Claude docs (under 200 lines), spec-kit -88%, sentry -69%. Note: arXiv 2605.10039 found no adherence effect of size for one rule, so the gain is cost and fewer conflicts, not attention. Cost: cheap to medium.
4. **Tag every remaining rule with what enforces it (`[gate:<id>]`, `[ci:<target>]`, `[review]`) and add a test that fails when a tag names a gate or target that does not exist.** Source: PostHog `test_agents_md_enforcement_tags.py`. This makes "75% not followed" visible per rule and stops stale tags. Cost: cheap.
5. **Put agent-neutral checks in git hooks and `make check`, not in the agent router.** Git hooks run the same under Claude and Codex. Sources: sentry `prek`, next.js lint-staged, CE local pre-push using the same selector as CI. Candidates: secret scan, em dash lint, PR-body checks (run in CI on the PR, like zed's Danger). Cost: cheap.
6. **Write every gate and lint error as a remediation instruction.** Source: OpenAI ("we write the error messages to inject remediation instructions into agent context"), PostHog ("Put the migration playbook in the rule's `message:` field"), zed Danger (shows the exact `Release Notes:` block). Cost: cheap.
7. **Add a small eval cell for the setup itself.** Run `claude -p --setting-sources project,local` and `codex exec` with a private `CODEX_HOME` on 5 to 10 fixture tasks, one per gate, and grade side effects (files, git log, shim logs), not the reply text. Source: CE `tests/skill-eval-cell/README.md`; getsentry AXIS scenarios; Claude `skill-creator` evals. Run it before each release of the setup, not in every CI run (CE "What belongs where"). Cost: medium.
8. **Make phase gates a script that exits 1 when a required file is missing.** For example, `implement` refuses to start without `docs/specs/<slug>.md` and a ticket file. Source: spec-kit `check-prerequisites.sh` (`ERROR: plan.md not found`). Cost: cheap.
9. **Shrink the router to one small script per event, fail-open, one log line per decision, with a unit test per gate.** Target well under 1,000 lines. Source: gstack hook contracts (fail open, "Always exits 0", log each decision); beads 30-line deny scripts. Cost: large.
10. **Generate project context from tools, and stamp managed blocks with the commit they were verified against.** Sources: beads ADR-0001 (`bd prime` as single source, SKILL.md 3,306 to about 500 words), BMAD `<!-- bmad:context -->` "Verified ... against 3cae711e". Cost: cheap.
11. **Budget the skill listing.** Claude lists descriptions within 1% of context (1,536 characters per skill); Codex within 2% or 8,000 characters. Remove overlapping skills (two catalogs for the same task), set rarely used ones to name-only, and measure trigger rate. Sources: Claude skills docs, `D-codex.md`, Anthropic tool search (defer at 10+ tools), Vercel (56% never invoked). Cost: medium.
12. **Adopt a rule-admission process and a doc gardener.** A new rule must be non-obvious, seen more than once, and specific; agents propose additions in the PR body, the owner merges them. A CI step finds dead links, stale references and oversize files. Sources: zed "Rules Hygiene", wshobson `tools/doc_gardener.py`, Claude `/doctor prompt-audit`. Cost: cheap.

Five things NOT to copy:

1. **gstack's scale** (35 workflows, 1,554 test files, 10 hosts, about 3,000 lines of hook code). It needs a team; one owner will carry a red build.
2. **Prose "hooks" that the agent must run** (spec-kit extension hooks). The template itself says the block "alone does not run the hook". This is text, not enforcement.
3. **Large catalogs of agents, personas and skills** (wshobson 199 agents and 185 skills; SuperClaude; BMAD personas). They fill the listing budget and overlap.
4. **Long ALWAYS/NEVER lists and "Mandatory skill invocation" lists** (uv, PostHog). Vercel shows skill triggers depend on wording; IFScale shows accuracy falls as instruction count rises (68% at 500). Use checks instead.
5. **Self-growing or giant instruction files** (VS Code "learn!" appends to always-loaded files; a 275,332-byte nested `AGENTS.md`; next.js grew 1,019 to 4,859 words). Also skip tripwire rules aimed at outside contributors (ghostty joke file, zed README banner): they suit public repos with strangers, not one owner's agents.

### Could not confirm

- OpenAI harness-engineering post: direct fetch returned HTTP 403. Quotes come from a search summary and mirrors; the 1M lines / 3 engineers / 3.5 PRs per day figure is secondary.
- Vercel post: number of eval cases and models are not stated.
- arXiv 2606.15828: only three smell rates are on the abstract page; the other three come from PostHog's skill.
- arXiv 2605.10039: the number of instructions was not tested.
- Size of `bd prime` output and of the gstack and CE skill listings (not measured; I did not run downloaded code).
- gstack permission settings; BMAD phase-gate details; sentry's "CI check" for the frontend/backend PR split (the workflow I read only labels change type on `master`); n8n git hooks; ruff and uv CI rule mapping.
- PostHog skill count (tree response was truncated, so 121 is a lower bound).
- History numbers do not follow renames (zed `.rules` to `AGENTS.md`; next.js `CLAUDE.md` deletion). Peaks are sampled, not exact.
