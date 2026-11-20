# B. How popular public AI coding setups enforce behaviour

Date of research: 2026-11-20. Method: `gh api` reads of the default branch (main) of each repo. Downloads are in `plan-research/dl/`. I read the files. I did not run them.

Star counts on 2026-11-20:

| Repo | Stars | Note |
|---|---|---|
| obra/superpowers | 322,575 | plus prime-radiant-inc/superpowers-evals (150 stars), its eval lab |
| anthropics/claude-code | 156,413 | its `plugins/` folder is now only a README. The plugins moved to anthropics/claude-plugins-official (47,791 stars). I studied that repo for item 2. |
| anthropics/skills | 197,929 | |
| openai/codex | 135,967 | the root AGENTS.md and `.codex/skills/` were deleted on 2026-09-30 (PR #49713). I studied the last version too. |
| humanlayer/humanlayer | 12,919 | history was squashed on 2026-10-22. The old `.claude/commands` are at commit 77c7fe99ee (2025-11-12). |
| disler/claude-code-hooks-mastery | 3,991 | the top result of `gh search repos "claude code hooks" --sort stars`. Next: parcadei/Continuous-Claude-v3 (3,952), disler/claude-code-hooks-multi-agent-observability (1,571). |

No repo was missing. One substitution inside a repo: item 2 uses claude-plugins-official, because claude-code/plugins/ now holds only `plugins/README.md`, which says: "Anthropic's plugins are developed in claude-plugins-official".

---

## 1. obra/superpowers

### Always-loaded text

- `hooks/session-start` (90 lines, bash) reads `skills/using-superpowers/SKILL.md` (65 lines, 492 words) and injects it in full as `additionalContext`, wrapped in `<EXTREMELY_IMPORTANT>\nYou have superpowers. ...`. The wrapper adds about 30 words.
- The harness also lists the 15 skill descriptions: 372 words in total.
- Total always loaded: about 894 words. Instruction count in using-superpowers: about 8 rules plus a 12-row "Red Flags" table of rationalizations.
- `AGENTS.md` (121 lines, 1,564 words) is for contributors to this repo only. It is not part of the plugin.

Key wording (using-superpowers/SKILL.md):
> "If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill."
> "Invoke relevant or requested skills BEFORE any response or action"
> `<SUBAGENT-STOP>` "If you were dispatched as a subagent to execute a specific task, ignore this skill."

The descriptions follow one shape: "Use when <trigger>, before <action>". Example: "Use when implementing any feature or bugfix, before writing implementation code".

### Enforcement table

| Mechanism | What it enforces | Agent can bypass? | Fails open or closed |
|---|---|---|---|
| Agent hook: SessionStart (`hooks/hooks.json`, matcher `startup\|clear\|compact`) | Injects using-superpowers at start, after /clear and after compaction | Yes, it is text only | Open: on a read error it injects "Error reading using-superpowers skill" and exits 0 |
| Instruction text (using-superpowers) | "Skill check before any action" | Yes | Open |
| Skills on demand (15 skills) | Process: TDD, debugging, plans, review | Yes | Open |
| Subagent prompts (subagent-driven-development: implementer, task reviewer, re-review) | Separate review of each task | Partly: the controller can skip the dispatch | Open |
| Test: `tests/skill-size/test-skill-size.sh` | Each SKILL.md is under 20,000 bytes (the compaction re-attach cut) | No, when run | Closed, but no CI runs it in this repo |
| Pre-commit (`.pre-commit-config.yaml`) | ruff, ruff format, ty on `evals/*.py` only | `--no-verify` | Closed for that path |
| Human review (AGENTS.md, PR template) | "94% PR rejection rate"; a human-written summary; disclosure of model and harness | No | Closed (maintainers close PRs) |

There is no `.github/workflows/` in obra/superpowers. The eval repo has one CI workflow (`test.yml`) that runs only static gates (`bun run check`, `bun run quorum check`).

### Hook design

- 1 hook command, 1 event (SessionStart). 169 lines of hook code: `hooks/session-start` 90 lines bash plus `hooks/run-hook.cmd` 79 lines (a polyglot cmd/bash launcher for Windows).
- No PreToolUse, no Stop, no UserPromptSubmit hooks. No deny path at all.
- The script has no fork and no external command, for speed under Git Bash ("a fork costs tens of milliseconds"). It emits one JSON shape per harness (Cursor, Claude Code, Copilot CLI, Muse).
- Kill switch: uninstall the plugin. No env switch.
- Tests of the hook: `tests/hooks/test-session-start.sh` (13,993 bytes) and `tests/hooks/test-run-hook-cmd-windows.sh`.

### Behaviour tests (the strongest of the 6)

- `prime-radiant-inc/superpowers-evals`, cloned into `evals/`: 95 scenarios. The harness "Quorum" drives real CLIs (Claude Code, Codex, Gemini) in tmux. An LLM actor types the user turns. Grading is by acceptance criteria plus deterministic post-checks on a normalized `trajectory.json`.
  Example `scenarios/triggering-test-driven-development/checks.sh`:
  `check-transcript skill-before-implementation-tool superpowers:test-driven-development Edit`
- `tests/explicit-skill-requests/` (9 prompt files): `claude -p` with stream-json, then `grep -q '"name":"Skill"'`, and a check that no other tool ran before the first Skill call.
- `tests/systematic-debugging/pressure-scenarios/` (3 pressure tests plus a CREATION-LOG): scenarios with time pressure and sunk cost ("Revenue loss: $15,000/minute").
- `skills/writing-skills/SKILL.md` makes skill writing into TDD: "If you didn't watch an agent fail without the skill, you don't know if the skill teaches the right thing." RED is a baseline run without the skill. The author records the agent's rationalizations verbatim and adds counters.
- New harness acceptance test (AGENTS.md): in a clean session, send "Let's make a react todo list". The `brainstorming` skill must trigger before any code.
- `docs/testing.md`: live evals are slow (3 to 30+ minutes each). Only static gates are safe for public CI.

### Worth copying

The "match the form to the failure" table in writing-skills. A discipline failure gets a prohibition plus a rationalization table. A wrong output shape gets a positive recipe. An omitted element gets a REQUIRED slot in a template. A conditional rule gets "an observable predicate". It also says: "if it's enforceable with regex/validation, automate it - save documentation for judgment calls". Plus the trajectory check "skill called before the first Edit/Write".

### Avoid

Shouting as the main lever (`EXTREMELY_IMPORTANT`, "1% chance", "ABSOLUTELY MUST"). The project itself found that prohibitions backfire on output-shape problems ("the prohibition arm produced clearly more of the unwanted content than the recipe arm"). Anthropic's skill-creator calls all-caps MUSTs "a yellow flag".

---

## 2. anthropics/claude-code (and anthropics/claude-plugins-official)

### Always-loaded text

- `anthropics/claude-code/CLAUDE.md`: 40 lines, 331 words, 3 numbered rules plus 2 short rules. All of it is about one topic: the security settings of GitHub Actions jobs that call Claude. Each rule names the CI check that enforces it: "`.github/workflows/workflow-hardening.yml` fails when a job ... breaks protection 1 or 3 ... Do not skip or weaken the check."
- `.claude/` of the repo: 3 commands only (`commit-push-pr.md`, `dedupe.md`, `triage-issue.md`). No hooks, no agents, no skills, no settings.json.
- Plugins always load only their skill and agent descriptions. Example: pr-review-toolkit `silent-failure-hunter` has a long description with 3 `<example>` blocks.

### Enforcement table

| Mechanism | What it enforces | Agent can bypass? | Fails open or closed |
|---|---|---|---|
| CI: `workflow-hardening.yml` -> `.github/scripts/check_workflow_hardening.py` | Firewall runner, `mode: enforce` allow list, `--permission-mode auto` on every Claude step | No (required check) | Closed |
| CI: `non-write-users-check.yml` | Posts a warning comment when a PR adds `allowed_non_write_users` | No | Open (comment only) |
| CI: `mod-tests.yml` | `tsc -p mods/tsconfig.json`, then `claude plugin test <mod>` per mod | No | Closed (skips the test step if the CLI has no `plugin test`) |
| Runner sandbox: `runs-on: ubuntu-24.04-firewall` + `.github/egress-firewall.yaml` | Network egress of agent jobs | No | Closed |
| Permission mode `--permission-mode auto`, `--disallowedTools` in workflow `claude_args` | Tool calls in CI agents | No | Closed |
| Command frontmatter `allowed-tools` (commands commit.md, commit-push-pr.md, code-review.md) | Which Bash prefixes the command may run, for example `Bash(git add:*)` | No, inside that command | Closed |
| Subagent with restricted tools (feature-dev `code-reviewer`: `tools: Glob, Grep, LS, Read, ...` with no Edit or Write) | Reviewers cannot edit | No | Closed |
| Agent hooks in plugins (below) | Security patterns, rules from files, loops | See below | Mostly open |
| CI in claude-plugins-official: `validate-plugins.yml`, `scan-plugins.yml`, `check-mcp-urls.yml`, `validate-licenses.yml`, `close-external-prs.yml` | Plugin folder shape, frontmatter of agents, skills and commands, marketplace.json | No | Closed |
| Human review | PRs from outside are closed automatically (`close-external-prs.yml`) | No | Closed |

### Hook design in the official plugins (claude-plugins-official/plugins)

| Plugin | Hook commands | Events | Code | Deny style | Tests |
|---|---|---|---|---|---|
| hookify | 4 | PreToolUse, PostToolUse, Stop, UserPromptSubmit (no matcher) | 847 lines Python: 4 entry scripts of 54 to 66 lines + `core/rule_engine.py` 313 + `core/config_loader.py` 297 | JSON `permissionDecision: "deny"` (PreToolUse) or `decision: "block"` (Stop) | none in the repo |
| security-guidance | 9 | SessionStart (timeout 180), UserPromptSubmit, PostToolUse (matcher `Edit\|Write\|MultiEdit\|NotebookEdit`, timeout 60; and `Bash` with `"if": "Bash(git*commit*)"`, `Bash(git*push*)`, `Bash(gt *)`), Stop | 15,170 lines (Python + sh); the main file `security_reminder_hook.py` is 3,758 lines | Stop: exit 2 or `asyncRewake` with a `rewakeMessage`; PostToolUse: `additionalContext` warnings | 79 pytest files under `plugins/security-guidance/tests/` |
| ralph-loop | 1 | Stop | `stop-hook.sh` 191 lines | `"decision": "block"` until `max_iterations` or a completion promise | none |
| claude-security | 6 | UserPromptExpansion (matcher `^claude-security:claude-security$`), PostToolUse with `"if": "Bash(git push *)"`, `"if": "Bash(gh pr create *)"` | 492 lines Python + 31 sh | tips only, `\|\| true` | none seen |
| explanatory-output-style, learning-output-style | 1 each | SessionStart | small sh | text injection | none |

Details:
- hookify is a generic rule engine. Rules are Markdown files `.claude/hookify.<name>.local.md` with frontmatter `event: bash|file|stop|prompt`, `pattern:` (regex), `action: warn|block`. Example `examples/dangerous-rm.local.md`: `pattern: rm\s+-rf`, `action: block`. One entry script per event, one shared engine.
- hookify fails open by design: every entry script ends in `finally: sys.exit(0)` with the comment "ALWAYS exit 0 - never block operations due to hook errors". Import errors become a `systemMessage`.
- security-guidance is one script for all its events (a router for one domain). It has kill switches in env: `SECURITY_GUIDANCE_DISABLE=1` (master), `ENABLE_PATTERN_RULES=0`, `ENABLE_CODE_SECURITY_REVIEW=0`, `ENABLE_COMMIT_REVIEW=0`, `ENABLE_STOP_REVIEW=0`. It has a `debug_log` with a size cap (`DEBUG_LOG_MAX_BYTES`). It fails open when state is unreadable ("State unavailable -> fail-open"). UserPromptSubmit is used only to snapshot a git baseline SHA, not to read the prompt.
- The `"if": "Bash(git*commit*)"` field on a hook entry uses permission-rule syntax. The hook process starts only for matching commands. This removes the need for a router that runs on every Bash call.
- `asyncRewake` runs the review in the background and wakes the agent with findings later. The Stop wall does not block the user at the end of the turn.
- New in the claude-code repo: `mods/` (function hooks in TypeScript, `register.ts`, for example `mods/sec-default`, `mods/agents-md`) with 461 test-related files and `claude plugin test`. These are engine extensions for organizations, not a pattern for one owner.

What goes where in the official plugins:
- Hooks: deterministic checks on tool calls (regex), background reviews, loops, context injection of a style.
- Commands: one workflow with `allowed-tools` and `!` shell context (`!`git status``). Example: code-review.md launches 4 parallel review agents, then one validator subagent per issue.
- Agents: narrow reviewers with `tools:` lists and `model:` (haiku, sonnet, opus).
- Skills: only `hookify/skills/writing-rules/SKILL.md` among the 6 named plugins.

### Behaviour tests

Hook unit tests yes (security-guidance: 79 files; mods: `claude plugin test`). Agent-behaviour evals: none found in either repo.

### Worth copying

The CLAUDE.md pattern "rule text + the name of the CI check that fails + do not weaken the check". The text explains, the check enforces. Also `"if": "Bash(git push *)"` on the hook entry, so each check runs only where it applies.

### Avoid

hookify as shipped: regex rules in loose files, always fail open, and no tests. The prompt field also looks wrong: `rule_engine.py` line 228 reads `input_data.get('user_prompt', '')`, but the Claude Code UserPromptSubmit input field is `prompt` (see Could not confirm). An untested rule engine can miss silently for months.

---

## 3. anthropics/skills

### Always-loaded text

- Only skill metadata. 20 SKILL.md files (19 skills + `template/SKILL.md`). Their descriptions total 988 words, an average of 49 words each.
- `skills/skill-creator/SKILL.md`: 485 lines, 5,205 words. It loads only when the skill triggers.
- No CLAUDE.md, no AGENTS.md, no hooks, no `.github/` in the tree.

### Guidance (skill-creator)

- Progressive disclosure, three levels: "1. Metadata (name + description) - Always in context (~100 words)"; "2. SKILL.md body - In context whenever skill triggers (<500 lines ideal)"; 3. bundled resources, read when needed.
- Description wording: "This is the primary triggering mechanism". "Claude has a tendency to 'undertrigger' skills ... please make the skill descriptions a little bit 'pushy'". All "when to use" information goes in the description, not in the body.
- Triggering limit: "Claude only consults skills for tasks it can't easily handle on its own - simple, one-step queries like 'read this PDF' may not trigger a skill even if the description matches perfectly".
- Tone: "If you find yourself writing ALWAYS or NEVER in all caps ... that's a yellow flag - ... explain the reasoning". "Explain the why."
- Hard limits in `scripts/quick_validate.py` (102 lines): name at most 64 characters, description at most 1,024 characters, compatibility at most 500 characters.

### Evaluation tooling

- Trigger evals: 8 to 10 should-trigger and 8 to 10 should-not-trigger queries. "The most valuable ones are the near-misses". Queries must be realistic, with paths, typos and backstory.
- `scripts/run_eval.py` (310 lines) writes a temporary command into `.claude/commands/` and runs `claude -p` for each query. `scripts/run_loop.py` splits 60% train and 40% held-out test, runs each query 3 times, iterates up to 5 times, and picks `best_description` "by test score rather than train score to avoid overfitting".
- Output evals: with-skill and without-skill runs, a grader subagent (`agents/grader.md`), a comparator, an analyzer that flags "assertions that always pass regardless of skill (non-discriminating)", and an HTML viewer for a human.

### Enforcement table

| Mechanism | What it enforces | Bypass? | Fails |
|---|---|---|---|
| Skill on demand | Workflow for that domain | Yes | Open |
| Description (always loaded) | When the skill triggers | Yes | Open (undertrigger is the known failure) |
| Script `quick_validate.py` | Frontmatter limits | Only if not run | Closed when run |
| Human review step | The eval viewer goes to the human before the agent revises the skill | Yes | Open |

No CI, no git hooks, no agent hooks.

### Worth copying

The trigger eval with near-miss negatives and a held-out split. It measures the one thing a description controls.

### Avoid

"Pushy" descriptions without the eval loop. Without measurement, pushy wording for one skill steals triggers from others.

---

## 4. openai/codex

### Always-loaded text

- Today: no root AGENTS.md. 4 nested AGENTS.md files, 79 lines and 587 words in total. Codex loads one only when the working directory is at or below its folder:
  - `codex-rs/code-mode-host/AGENTS.md`: 3 lines, 25 words ("Do not use timeouts or sleeps to synchronize tests").
  - `codex-rs/exec-server/src/sandbox_integrity/AGENTS.md`: 48 lines, 357 words ("scope and review contract").
  - `codex-rs/rollout-trace/AGENTS.md`: 16 lines, 130 words.
  - `codex-rs/tui/src/bottom_pane/AGENTS.md`: 12 lines, 75 words.
- Until 2026-09-30: root `AGENTS.md`, 320 lines, 3,128 words, about 122 bullet rules in 30 headings (Rust style, clippy rules, test style, snapshot tests, "Change size guidance (800 lines)", app-server API rules). Plus 11 skills in `.codex/skills/` (for example `babysit-pr` with a 951-line `gh_pr_watch.py` and a 285-line test). PR #49713 deleted all of it with no reason in the body ("Delete the root `AGENTS.md`, the skills under `.codex/skills/` ..."). The commit has a `GitOrigin-RevId`, so the repo is now a mirror of an internal repo.
- Codex loading rule (official docs): files concatenate from the root down, one per directory, `AGENTS.override.md` first; `project_doc_max_bytes` defaults to 32 KiB.

Content kinds in the old root file: many rules were mirrors of a lint ("Always collapse if statements per .../clippy/...#collapsible_if"), or of a CI check ("CI verifies lockfile drift"), or of a custom lint (`argument_comment_lint`: "Most of the time, it is best to update the PR and let CI take responsibility for checking this").

### Enforcement table

| Mechanism | What it enforces | Bypass? | Fails |
|---|---|---|---|
| CI `blocking-ci.yml` -> job "CI required" -> `.github/scripts/check_ci_results.py` | One required gate over Bazel, blob size, cargo-deny, codespell, repo-checks, rust-ci, sdk | No | Closed |
| CI `repo-checks.yml` | `verify_tui_core_boundary.py` ("codex-tui does not import codex-core directly"), `verify_cargo_workspace_manifests.py`, `verify_bazel_clippy_lints.py`, README ASCII and ToC, formatting | No | Closed |
| CI `blob-size-policy.yml` -> `scripts/check_blob_size.py` | No large blobs | No | Closed |
| CI `rust-release-argument-comment-lint.yml` + `just argument-comment-lint` | `/*param_name*/` comments on opaque literals (custom lint) | No | Closed |
| Lint: clippy with workspace lints, `cargo-deny`, `codespell`, `.markdownlint-cli2.yaml`, `ruff.toml`, prettier | Style, deps, spelling | No | Closed |
| Sandbox (product): `SandboxMode` = `read-only` (default), `workspace-write`, `danger-full-access` (`codex-rs/protocol/src/config_types.rs`) | File and network reach of the agent | Only with user approval | Closed |
| Sandbox protected paths: `.git`, `.agents`, `.codex` stay read-only under a writable root (`codex-rs/protocol/src/permissions.rs` lines 51 to 53, 891 to 893) | The agent cannot edit its own config, skills, hooks or git metadata | No | Closed |
| Exec policy rules (product): Starlark `.rules` files, `prefix_rule` with `decision` = `allow`, `prompt` or `forbidden`; "the most restrictive decision" wins | Shell commands | No | Closed |
| Hooks (product): `hooks.json` or `[hooks]` in config.toml; events PreToolUse, PermissionRequest, PostToolUse, UserPromptSubmit, Stop, SessionStart and more | Custom checks | Depends | "A PreToolUse error, timeout, or malformed response can let the tool run": open |
| Instruction text (nested AGENTS.md) | Local contracts | Yes | Open |
| Human review | PR template, CLA, `close-stale-contributor-prs.yml` | No | Closed |

### Hook and rule design (product docs)

- Rules have inline tests: "`match` and `not_match` act as inline unit tests that Codex checks when it loads the rules". `codex execpolicy check --pretty --rules <file> -- gh pr view 7888` prints the decision as JSON.
- Hooks: matcher is a regex; `UserPromptSubmit`, `Stop` and `Interrupt` have no matcher. Deny: `permissionDecision: "deny"` with a reason, or exit code 2 with the reason on stderr. Timeout default 600 seconds (SessionEnd and Interrupt: 1 second, max 3).
- Trust step: "Non-managed hooks must be reviewed and trusted before they run". Trust is recorded against the hook's hash, so a changed hook needs a new review (`/hooks`).
- Kill switch: `[features] hooks = false` in config.toml.
- The repo has 66 files under `codex-rs/hooks/`, including generated JSON schemas for each event input and output (`schema/generated/*.schema.json`) and a fixture writer.

### Behaviour tests

None found in the repo for agent behaviour on the repo itself. Could not confirm internal evals.

### Worth copying

Turn each AGENTS.md rule that a tool can check into a CI script, then delete the text. Example: the import boundary rule became `verify_tui_core_boundary.py`. Also: protect `.git`, `.codex`, `.agents` from the agent by sandbox, not by text.

### Avoid

A 3,128-word root file in which most lines repeat clippy and CI rules. The maintainers deleted it in one PR.

---

## 5. humanlayer/humanlayer

### Always-loaded text

- `CLAUDE.md`: 278 lines, 2,228 words. `AGENTS.md` is a 9-byte symlink to CLAUDE.md (the `Makefile` target `setup` runs `ln -s CLAUDE.md AGENTS.md`).
- It has 15 conditional blocks of the form `<important if="you are running tests or typechecks">`. They tell the model when a block applies.
- 7 more nested CLAUDE.md files under `apps/` and `packages/` (load only in those folders), for example `apps/riptide-ui/CLAUDE.md` (6,025 bytes).
- 28 skills in `.claude/skills/` with 613 words of descriptions.
- The RPI plugin (`apps/riptide-rpi-claude-plugin/`) has 22 skills. 21 of them have the description "Only use when the user explicitly invokes this skill by name." So they add about 11 words each to context and never trigger by themselves.
- History: at commit 77c7fe99ee (2025-11-12) CLAUDE.md was 88 lines, 449 words. It grew 5 times in one year.

### Enforcement table

| Mechanism | What it enforces | Bypass? | Fails |
|---|---|---|---|
| CI `ci.yml` ("Check, Build, Test") | `bun run typecheck`, `bun run check:zod`, `bun run quality`, `cargo check`, `cargo test --lib`, tests | No | Closed |
| Agent hook script `.claude/hooks/block-test-output-filtering.sh` (45 lines) | Denies `test`, `typecheck`, `oxlint` commands piped to `head`, `tail`, `grep`, `sed`, `awk` | Agent can run the command another way | Exit 2 with a reason on stderr |
| Agent hook script `.claude/hooks/stop-checks.sh` (25 lines) | At Stop: prebuild, `hook:quality`, `turbo run typecheck` must pass; skips during a merge with a message | No, while registered | Closed (exit 2 with the output) |
| Permission allow list (`.claude/settings.json`) | Only `scripts/spec_metadata.sh` is pre-allowed | n/a | n/a |
| Instruction text with conditions (`<important if=...>`) | Context-specific rules | Yes | Open |
| Skills invoked by name only (RPI) | Research, plan, implement phases are human-started | n/a | n/a |
| Subagents with restricted tools (2025 version) | `codebase-locator`: `tools: Grep, Glob, LS`; 6 agents | No | Closed |
| Human review | Linear statuses "research in review", "plan in review", "code review" | No | Closed |
| `vouch-check-pr.yml`, `vouch-check-issue.yml` | Contributor vouching | No | Closed |

Note: the 2 hook scripts exist, but the committed `.claude/settings.json` (13 lines) registers no hooks. They are wired somewhere else (see Could not confirm).

### Hook design

One script per rule. 70 lines of shell in total. Each script reads stdin, decides, and exits 2 with a short reason that tells the agent what to do instead ("use the <persisted_output> path from the tool result and filter that file instead"). No log, no kill switch, no tests.

The same rule is also in CLAUDE.md as text ("you must NEVER pipe the output of test commands to head/tail/grep/etc"). So text explains, hook enforces.

### The 2025 setup (the one that made the repo known)

27 commands in `.claude/commands/` (for example `research_codebase.md` 11,181 bytes, `create_plan.md` 14,687 bytes, `implement_plan.md` 3,165 bytes, `validate_plan.md`) and 6 agents with tool lists. Each phase writes a document to `thoughts/`. A human reviews the document before the next phase. That flow now lives in the RPI plugin as explicit-only skills.

### Behaviour tests

None found.

### Worth copying

A Stop hook that runs the real typecheck and lint and exits 2 with the output. It is short (25 lines), it is deterministic, and the agent cannot finish with red checks. Also: skills that only run when the human names them, for heavy phases.

### Avoid

Letting CLAUDE.md grow from 449 to 2,228 words. Also keeping hook scripts in the repo that the committed settings do not register: a reader cannot tell if the rule is active.

---

## 6. disler/claude-code-hooks-mastery

### Always-loaded text

- `CLAUDE.md`: 0 bytes.
- `session_start.py` can inject `.claude/CONTEXT.md`, `.claude/TODO.md`, `TODO.md` as `additionalContext`, but only with `--load-context`. The settings do not pass that flag.
- 19 agents (13 of them crypto demos), 14 commands, 8 output styles, 9 status line scripts. README 41,392 bytes.

### Enforcement table

| Mechanism | What it enforces | Bypass? | Fails |
|---|---|---|---|
| PreToolUse hook `pre_tool_use.py` (138 lines) | Denies `.env` access (Read, Edit, Write, Bash) and `rm -rf` variants by regex | Yes, with other commands (regex) | Exit 2 on a match; any exception exits 0: open |
| UserPromptSubmit hook `user_prompt_submit.py` (191 lines) | Logs prompts; `validate_prompt()` has an empty `blocked_patterns` list; runs with `--log-only` | n/a | Open |
| Hooks scoped in command or agent frontmatter | `plan_w_team.md` has Stop hooks `validate_new_file.py --directory specs --extension .md` and `validate_file_contains.py --contains '## Task Description'`; agent `builder` has PostToolUse `ruff_validator.py`, `ty_validator.py` on `Write\|Edit` | No, while that command or agent runs | Closed (exit 2) |
| Subagent with restricted tools | `validator`: `disallowedTools: Write, Edit, NotebookEdit` | No | Closed |
| Permission allow list | 12 allow rules (`Bash(mkdir:*)`, `Write`, `Edit`, ...); `deny: []` | n/a | n/a |
| CI, git hooks, tests | none | | |

### Hook design

- 13 hook commands, one per event (PreToolUse, PostToolUse, Notification, Stop, SubagentStop, UserPromptSubmit, PreCompact, SessionStart, SessionEnd, PermissionRequest, PostToolUseFailure, SubagentStart, Setup). Each has `"matcher": ""` (all tools).
- 3,139 lines of Python in `.claude/hooks/` (13 event scripts plus 4 validators), plus LLM and TTS helpers in `hooks/utils/`. Each is a `uv run --script` single file with inline dependencies.
- Logging: each script appends to `logs/<event>.json` by reading the whole JSON list, appending, and writing it again.
- No timeouts set (default applies). No kill switch. No tests. No CI (no `.github/`).

### Behaviour tests

None.

### Worth copying

Hooks in the frontmatter of a command or an agent. The check runs only while that workflow runs (for example: the plan command cannot stop until `specs/*.md` exists and contains `## Task Description`).

### Avoid

A hook on every event with `matcher: ""` and a full JSON rewrite per call. It adds a `uv run` start-up to every tool call, and it is a demo, not a guardrail.

---

## Cross-repo synthesis

### Summary table

"Always-loaded words" counts the text the agent gets in every session from that setup (instruction files plus injected text plus skill descriptions). Hook commands count entries in hooks configuration.

| Setup | Always-loaded words | Hook commands | Lines of hook code | Skills | CI enforcement | Behaviour tests |
|---|---|---|---|---|---|---|
| obra/superpowers | ~894 (492 injected skill + ~30 wrapper + 372 descriptions) | 1 (SessionStart) | 169 | 15 | no (only the eval repo runs static checks) | yes (95 Quorum scenarios, claude -p trigger tests, pressure scenarios) |
| anthropics/claude-code + claude-plugins-official | 331 (repo CLAUDE.md); plugins add descriptions only | 0 in repo; plugins: hookify 4, security-guidance 9, ralph-loop 1, claude-security 6 | hookify 847; security-guidance 15,170; ralph-loop 191 | 1 in the 6 named plugins | yes | hook unit tests yes (79 files); agent evals no |
| anthropics/skills | 988 if all 20 installed (~49 per skill) | 0 | 0 | 20 | no | tooling yes (trigger and output evals via claude -p); no stored results or CI |
| openai/codex | 0 at root now (was 3,128); 587 in 4 nested files, loaded by folder | 0 in repo | 0 | 0 now (was 11) | yes (strongest) | no |
| humanlayer/humanlayer | ~2,850 (CLAUDE.md 2,228 + 613 skill descriptions; RPI plugin adds ~11 words per skill) | 2 scripts (registration not in committed settings) | 70 | 28 + 22 | yes | no |
| disler/claude-code-hooks-mastery | ~0 (empty CLAUDE.md) + agent and command descriptions | 13 | 3,139 | 0 | no | no |

### 10 patterns that appear in 2 or more repos (most common first)

1. **Narrow subagents with tool limits for review and research** (5): claude-plugins-official (feature-dev `code-reviewer` without Edit or Write; pr-review-toolkit), humanlayer (2025 agents `tools: Grep, Glob, LS`), disler (`validator` with `disallowedTools`), superpowers (implementer and reviewer prompts in subagent-driven-development), codex (old `code-review-*` skills as separate passes).
2. **CI is the real gate; instruction text points at it** (4): claude-code (CLAUDE.md names `workflow-hardening.yml`), codex (blocking-ci, repo-checks, custom lints; old AGENTS.md: "let CI take responsibility"), humanlayer (`ci.yml`), claude-plugins-official (`validate-plugins.yml`).
3. **Small always-loaded text; detail goes in on-demand skills or files** (4): anthropics/skills (~100 words metadata, <500 lines body), superpowers (one bootstrap skill, rest on demand, 20,000-byte cap per SKILL.md tested), codex (root file deleted, nested files by folder), claude-code (331-word CLAUDE.md on one topic).
4. **Stop-time check that blocks the end of the turn** (4): humanlayer `stop-checks.sh` (exit 2 with typecheck output), security-guidance (Stop review, exit 2 or `asyncRewake`), ralph-loop (`decision: "block"` until `max_iterations`), disler (Stop validators in `plan_w_team.md` frontmatter). hookify has one too (`require-tests-stop`, `enabled: false` by default).
5. **One script per rule or per event, not one router for everything** (4): humanlayer (2 scripts, one rule each), disler (one script per event), hookify (one entry script per event), superpowers (one script). Exception: security-guidance uses one 3,758-line script for 4 events, but for one domain only.
6. **Deny with exit 2 or `permissionDecision: "deny"`, plus a reason that says what to do instead** (4): humanlayer, disler, hookify, Codex hooks docs.
7. **Command or skill frontmatter limits tools** (3): claude-plugins-official (`allowed-tools: Bash(git add:*) ...`), claude-code repo `.claude/commands/commit-push-pr.md`, disler (`disallowed-tools: Task, EnterPlanMode` in `plan_w_team.md`).
8. **Measured agent behaviour (real CLI runs, transcript checks)** (2): superpowers (Quorum, `claude -p` trigger tests), anthropics/skills (`run_eval.py`, `run_loop.py` with train and test split).
9. **Narrow hook matching so a check runs only where it applies** (3): claude-plugins-official (`"if": "Bash(git push *)"`, matcher `Edit|Write|MultiEdit|NotebookEdit`), disler (hooks in command and agent frontmatter), Codex (regex matcher per event).
10. **Env or config kill switch for hooks** (2): security-guidance (`SECURITY_GUIDANCE_DISABLE=1` and 4 per-feature switches), Codex (`[features] hooks = false`). Superpowers and humanlayer have none.

Also seen in 2 repos: tests of the hook code itself (superpowers `tests/hooks/`, security-guidance 79 pytest files); human review between phases (humanlayer Linear statuses, superpowers "show your human partner the complete diff").

### "Reminder router" patterns: who uses them

| Pattern | Used by | Notes |
|---|---|---|
| Regex on the user prompt to inject reminders | Nearly none. hookify supports `event: prompt` rules with `action: warn`, but the output is a `systemMessage`, and the code reads the field `user_prompt` (see Could not confirm). disler's prompt hook has an empty pattern list and runs `--log-only`. security-guidance uses UserPromptSubmit only for a git snapshot. | No repo injects reminders into the model's context based on prompt keywords. Superpowers solves the same need with skill descriptions plus one bootstrap at session start. |
| A miss log (a log of reminders that should have fired, or of rule misses) | None | security-guidance has a debug log and metrics; disler logs every event's raw JSON. Nobody logs misses. |
| Stop-time walls | Used by 4 (humanlayer, security-guidance, ralph-loop, disler) | Difference: each wall runs a deterministic check (typecheck, a file exists, a review) and exits 2 with that output. None of them blocks Stop because a reminder or a skill call is missing. ralph-loop caps itself with `max_iterations`. |
| One router for all events and all rules | None as a general router | hookify has one engine but one entry per event and rules in data files. security-guidance has one script for 4 events but one domain. Nobody puts unrelated rules (git, PR, docs, UI, SEO) behind one 5,000-line dispatcher. |

### Could not confirm

- Why openai/codex deleted its root AGENTS.md and `.codex/skills/` (PR #49713 gives no reason). The `GitOrigin-RevId` suggests the guidance moved to an internal repo, but I did not confirm this.
- Where humanlayer registers `.claude/hooks/stop-checks.sh` and `block-test-output-filtering.sh`. The committed `.claude/settings.json` has no `hooks` key. It may be a local or user settings file, or the plugin `apps/riptide-claude-code-plugin` (its hooks.json loads `./mod.ts`, which I did not read).
- That hookify prompt rules never match. `core/rule_engine.py` line 228 reads `input_data.get('user_prompt', '')`. My understanding is that Claude Code sends the prompt as `prompt`. I did not check the hooks reference in this session.
- Whether a hook `systemMessage` reaches the model or only the user. hookify uses it for warnings.
- Internal or private evals at OpenAI or Anthropic for these repos. None are in the public trees.
- The full content of superpowers-evals scenarios beyond the one I read (95 scenario folders counted by path).
- Codex sandbox defaults for network access and approval policies: the official pages I tried (`learn.chatgpt.com/docs/agent-configuration/sandboxing`) returned 404. I confirmed only the mode names and the protected paths from the source.
- Word counts of agent and command descriptions in disler and claude-plugins-official. I did not sum them.
