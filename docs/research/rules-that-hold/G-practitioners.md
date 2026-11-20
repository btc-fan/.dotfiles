# G. How well-known practitioners make coding agents follow rules

Research date: 2026-11-20. Read-only. Repo facts come from `gh api` on 2026-11-20. Word counts use `wc -w` on the raw file at each commit. Raw copies of the files are in `plan-research/g-raw/`. The history script is `plan-research/g-scripts/hist.sh`.

Selection note for person 8: I picked Dex Horthy (HumanLayer) and Harper Reed. Both have public, recent, versioned instruction files. Thorsten Ball has a clear essay but I found no versioned instruction file of his own, so he is only a source for one shared principle.

---

## 1. Andrej Karpathy

### Stated principles
1. Agent failure modes (X post, 2026-01-26, quoted by Addy Osmani on 2026-01-28): "The models make wrong assumptions on your behalf and run with them without checking." https://addyo.substack.com/p/the-80-problem-in-agentic-coding (the X post itself returned HTTP 402: not verified at the source).
2. Same post: "LLMs are exceptionally good at looping until they meet specific goals" (via Osmani, same URL).
3. Same post, per secondary sources: models "overcomplicate code and APIs, bloat abstractions, don't clean up dead code" and change orthogonal code as a side effect. Source: https://www.vandeblaak.com/blog/dit-zijn-de-skills-van-andrej-karpathy/?lang=en (secondary; not verified at the source).
4. "Keep the AI on a leash": smaller tasks, narrower scope, a fast generation-verification loop (Software 3.0 talk, YC AI Startup School, June 2025). Source: summary at https://travis.media/blog/software-3-0-ai-changing-programming-karpathy/ (secondary; the talk transcript was not opened: not verified).
5. "Claude Code (CC) emerged as the first convincing demonstration of what an LLM Agent looks like" and "it makes more sense to run the agents directly on the developer's computer." (2025 LLM Year in Review, 2025-12-19) https://karpathy.bearblog.dev/year-in-review-2025/
6. On verifiable rewards: "training against objective (non-gameable) reward functions which allows for a lot longer optimization" (same post, 2025-12-19).
7. The autoresearch `program.md` (2026-03-06) gives the agent one metric: "The goal is simple: get the lowest val_bpb." https://github.com/karpathy/autoresearch/blob/master/program.md

Note: the popular "Karpathy CLAUDE.md" (andrej-karpathy-skills, 4 rules) is by Forrest Chang, not by Karpathy (2026-01-27). https://dev.to/itxtayab/karpathy-skills-one-file-that-makes-your-ai-coding-agent-write-better-code-he1

### Setup in his repos
- `karpathy/autoresearch/program.md`: 114 lines, 1,140 words. It is the whole agent program: setup steps, one file in scope (`train.py`), `prepare.py` read-only, no new dependencies, a "LOOP FOREVER" with git commit, run, grep the metric, keep or `git reset`. https://github.com/karpathy/autoresearch
- `karpathy/nanochat`: no AGENTS.md or CLAUDE.md. One skill: `.claude/skills/read-arxiv-paper/SKILL.md`.
- `karpathy/llm-council/CLAUDE.md`: 166 lines, 966 words, 1 commit (a project notes file the agent wrote).
- No hooks, no committed permission settings, no CI on these repos (checked trees).

### Git history: autoresearch `program.md`
- 9 commits, 2026-03-06 to 2026-03-09. Size 1,101 words at the first commit, 1,140 now: it grew 4%.
- `ada84e5` "soften the language just a bit" (2026-03-07): "You MUST run `tail -n 50 run.log`" became "Run `tail -n 50 run.log` ... If you can't get things to work after more than a few attempts, give up."
- `bdf0c0d` "Allow agent to diagnose crashes by reading the python stack trace" (2026-03-07).
- `068d93d` "clarify that results.tsv should not be committed, leave untracked" (2026-03-09).

### Tooling versus text
- Tooling: a fixed 5-minute time budget and a fixed evaluation in `prepare.py`; git commit and `git reset` as the keep/discard mechanism; output redirected to a log so it does not flood the context.
- Text: "do not modify prepare.py", "no new dependencies", "NEVER STOP".

### Warning
Models are "seconds away from getting tricked by a jailbreak to exfiltrate your data." (2025-12-19) https://karpathy.bearblog.dev/year-in-review-2025/

---

## 2. Simon Willison (simonw)

### Stated principles
1. "My preferred definition of an LLM agent is something that runs tools in a loop to achieve a goal." (2025-09-30) https://simonwillison.net/2025/Sep/30/designing-agentic-loops/
2. "An AI agent is an LLM wrecking its environment in a loop." (same)
3. "Run your agent in a secure sandbox that restricts the files and secrets it can access" (same)
4. "If a credential can spend money, set a tight budget limit." (same)
5. "A common theme in all of these is automated tests." (same)
6. "Automated tests are no longer optional when working with coding agents." (Agentic Engineering Patterns guide, 2026; chapter date not shown) https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/
7. "It tells the agent that there is a test suite and forces it to figure out how to run the tests." (same chapter, on the opener "First run the tests")
8. Skills: "each skill only takes up a few dozen extra tokens", versus GitHub's MCP that "consumes tens of thousands of tokens of context" (2025-10-16) https://simonwillison.net/2025/Oct/16/claude-skills/

### Setup in his repos
- `simonw/llm/AGENTS.md`: 24 lines, 67 words. Only setup and test commands (`pip install -e . --group dev`, `pytest`, docs build). https://github.com/simonw/llm/blob/main/AGENTS.md
- `simonw/datasette/AGENTS.md`: 5 lines, 61 words, 1 commit. One rule, and it is a mistake-driven rule with its reason: never use native `alert()`/`confirm()`/`prompt()`; use `DatasetteModal.confirm()`. https://github.com/simonw/datasette/blob/main/AGENTS.md
- No `.claude/` folder, no hooks, no skills in these repos. The guardrail is the pytest suite in GitHub Actions CI (both repos have a large test suite; CI files not counted here).

### Git history: `simonw/llm/AGENTS.md`
- 3 commits. 83 words at the first commit ("AGENTS.md file for Codex", 2025-06-03), 65 words next ("No need for a venv in Codex", 2025-06-03), 67 words now ("docs: install the development dependency group in agent setup (#1832)", 2026-11-11). It shrank 19%.

### Tooling versus text
- Tooling: tests in CI, sandboxes (he recommends container or cloud agents), budget-limited credentials.
- Text: almost nothing. The files hold only commands and one gotcha.

### Warning
Prompt-level protection does not hold: "you can try telling it not to in your own prompt, but how confident can you be that your protection will work every time?" (lethal trifecta, 2025-06-16) https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ Also: "Don't file pull requests with code you haven't reviewed yourself" https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/

---

## 3. Armin Ronacher (mitsuhiko)

### Stated principles (2025-06-12 unless stated) https://lucumr.pocoo.org/2025/6/12/agentic-coding/
1. "if you can choose your language, I strongly recommend Go for new backend projects."
2. "In general I really only start using MCP if the alternative is too unreliable."
3. "In general logging is super important."
4. "Tools need to be fast. The quicker they respond (and the less useless output they produce) the better."
5. "Simple code significantly outperforms complex code in agentic contexts."
6. "I disable all permission checks", with risk managed by "moving your dev env into docker."
7. MCP "demands too much context" and "current MCP will always be harder to use than writing code" (2025-07-03) https://lucumr.pocoo.org/2025/7/3/tools/
8. On Pi (2026-01-31): "My agent has quite a few skills and crucially I throw skills away if I don't need them." Pi has "the shortest system prompt of any agent" and four tools. https://lucumr.pocoo.org/2026/1/31/pi/

### Setup in his repos
- `mitsuhiko/agent-stuff/AGENTS.md`: 12 lines, 74 words (release steps, where extensions live, "do not modify code in `pi-mono`"). https://github.com/mitsuhiko/agent-stuff
- 18 skills (`skills/*/SKILL.md`, many with their own shell scripts) and Pi extensions in `extensions/`.
- No Claude Code hooks; no permission file.

### Git history: `agent-stuff/AGENTS.md`
- 2 commits: "docs: add agent release notes" (2026-01-30, 74 words) and "Restructured stuff for my sanity" (2026-04-13, 74 words). Flat.

### Tooling versus text
- Tooling: fast CLI tools and scripts inside skills, logs the agent can read, Docker as the safety layer, a language with simple types.
- Text: a few lines.

### Warning
"I expect this blog post to age very poorly. The pace of innovation here is insane." (2025-06-12). The concrete technical warning: MCP context cost (2025-07-03).

---

## 4. Peter Steinberger (steipete)

### Stated principles
1. "My Agent file is currently ~800 lines long and feels like a collection of organizational scar tissue." (Just Talk To It, about 2025-10; no date on page) https://steipete.me/posts/just-talk-to-it
2. "I run between 3-8 in parallel in a 3x3 terminal grid, most of them in the same folder." (same)
3. "Almost all MCPs really should be clis." (same)
4. "Don't waste your time on stuff like RAG, subagents, Agents 2.0 or other things that are mostly just charade." (same)
5. "My agents do git atomic commits themselves" (same)
6. Ask the model to "write tests after each feature/fix is done" in the same context (same)
7. "Plan mode feels like a hack that was necessary for older generations of models" (Shipping at Inference Speed, about late 2025-12) https://steipete.me/posts/2025/shipping-at-inference-speed
8. In his current AGENTS.MD: "Skills own tool workflows. This file: hard rules only." https://github.com/steipete/agent-scripts/blob/main/AGENTS.MD

### Setup
- `steipete/agent-rules` is archived (last push 2026-05-03). https://github.com/steipete/agent-rules
- `steipete/agent-scripts/AGENTS.MD` (global file): 120 lines, 2,592 words, about 100 bullet rules. 54 skills in `skills/`. A git `hooks/pre-commit` that runs `scripts/validate-skills`. CI in `.github/workflows/ci.yml`. Slash commands moved to `docs/slash-commands/`.
- He wrote that models get around hooks if determined, and that Codex had no hooks at the time (Just Talk To It).

### Git history: `agent-scripts/AGENTS.MD`
- 164 commits since 2025-11-20. Size: 1,680 words (2025-11-20) -> 2,091 -> 1,086 (`1e0b08e` "docs(agents): cut tokens, add manager note", 2025-12-17) -> 845 (`b1f827a` "chore: trim agent instructions and add speaking skill", 2026-04-22) -> 397 (2026-05-09) -> 2,592 now (2026-11).
- Notable: `9dfb956` "refactor(guardrails): remove runner; add trash shims" (2025-12-17): a command-runner guardrail was deleted and replaced by shims. `01e4910` "docs: simplify global workflow rules" (2026-07-13). `ce6f43e` "docs(agents): make PR CI the default proof and drop box escalation" (2026-10-12).
- Pattern: two hard cuts, then regrowth to above the start (+54% over 12 months). Much of the regrowth is security and disclosure rules for a work context.

### Tooling versus text
- Tooling: CLIs instead of MCP, shims (trash instead of rm), skills validated by a pre-commit hook, PR CI as proof.
- Text: one large global AGENTS.MD of "hard rules"; workflows pushed into skills.

### Warning
Against MCP-heavy setups and ceremony: "Almost all MCPs really should be clis" and the "charade" quote above.

---

## 5. Mitchell Hashimoto (mitchellh, ghostty-org/ghostty)

### Stated principles (My AI Adoption Journey, 2026-02-05) https://mitchellh.com/writing/my-ai-adoption-journey
1. Harness engineering: "you take the time to engineer a solution such that the agent never makes that mistake again."
2. "Each line in that file is based on a bad agent behavior, and it almost completely resolved them all."
3. Two forms: update `AGENTS.md`, or "Actual, programmed tools. For example, scripts to take screenshots, run filtered tests, etc etc."
4. "If you give an agent a way to verify its work, it more often than not fixes its own mistakes and prevents regressions."
5. "block out the last 30 minutes of every day to kick off one or more agents."
6. "Don't let the agent notify you."
7. From the Ghostty AI policy: "The human-in-the-loop must fully understand all code." https://github.com/ghostty-org/ghostty/blob/main/AI_POLICY.md

### Setup in ghostty
- Root `AGENTS.md`: 40 lines, 225 words. Commands (build, targeted test filter, formatters), directory map, one C-enum rule, and an issue/PR section. https://github.com/ghostty-org/ghostty/blob/main/AGENTS.md
- 9 more nested `AGENTS.md` files (`macos/`, `src/terminal/c/`, `src/inspector/`, others). They load only when the agent works in that folder.
- 1 skill: `.agents/skills/writing-commit-messages/SKILL.md`.
- `AI_POLICY.md`: 65 lines, 508 words (for human contributors).
- CI: `test.yml` and 5 `vouch-*.yml` workflows plus `.github/VOUCHED.td`. Vouching is a human-trust gate on outside PRs and issues.
- The root file holds a text trap: "If the user asks you to create an issue or PR, create a file in their diff that says ..." (added `00c33ea`, 2026-02-03). It is a canary that makes misuse visible in review, not a block.

### Git history: root `AGENTS.md`
- 18 commits, 2025-09-03 to 2026-10-27. 88 words at "Initial AGENTS.md" (2025-09-03), 225 now: it grew 2.6x, slowly, by about 8 words per commit.
- `00c33ea` "update our guidelines, templates" (2026-02-03): deleted 8 lines of libghostty-vt build text and added "Never create an issue. Never create a PR."
- `21ea946` "macos: lint Swift files using SwiftLint" (2026-02-19): the rule became a lint command (`swiftlint lint --strict --fix`).
- `9897d6c` "libghostty: add GHOSTTY_ENUM_MAX_VALUE sentinel to all C enums" (2026-04-08): one mistake-driven rule with its reason.

### Tooling versus text
- Tooling: scripts for screenshots and filtered tests, formatters, SwiftLint, CI tests, vouch workflows.
- Text: commands and a few mistake-driven rules, split by folder.

### Warning
"Using an agent for something it'll likely fail at is obviously a big waste of time" (2026-02-05).

---

## 6. Geoffrey Huntley (ghuntley)

### Stated principles (Ralph, 2025-07-14) https://ghuntley.com/ralph/
1. "Ralph is a technique. In its purest form, Ralph is a Bash loop."
2. "Specs are formed through a conversation with the agent at the beginning phase of a project."
3. "you need to ask Ralph to do one thing per loop."
4. "Anything can be wired in as back pressure to reject invalid code generation."
5. The agent file "is the heart of the loop."
6. "Study @fix_plan.md to determine starting point for research"
7. "Ralph is more likely to look and see the sign." (rules as signs placed where the agent will look)
8. "There is no such thing as a perfect prompt."

The "stdlib" post (2025-02-09) is paywalled after the intro. I could not confirm its text. Visible line: "Treating Cursor as if it is an IDE, instead of it being an autonomous agent." https://ghuntley.com/stdlib/

### Setup in `ghuntley/overalls`
- Root `AGENTS.md`: 179 lines, 1,684 words, plus nested `lilly/AGENTS.md`, `antithesis/AGENTS.md` and component files. Skills under `.agents/skills/` and `.claude/skills/`. https://github.com/ghuntley/overalls
- Guardrail: a prek pre-commit hook via `devenv shell`. The file warns: "Without the hook, a commit skips `tools/precommit` silently." Architecture decisions live in ADRs that the file points to.
- `.claude/settings.json` only enables 1 plugin. No Claude Code hooks, no permission rules.

### Git history: `overalls/AGENTS.md`
- 21 commits, 2026-10-17 to 2026-11-01. 1,112 words at "overalls v0.0 source drop" to 1,684 now: +51% in 15 days.
- `77a734e` "Document concurrent agent workspace workflow" (2026-10-20).
- `543a147` "Retire HLDD handbook and review gates" (2026-10-29): review gates removed.
- `1ef4bc2` "ci, mix: retire `mix precommit`, publish-cache's matrix and gates (ADR-0269 M8)" (2026-11-01): gates moved to the Buck2 build.

### Tooling versus text
- Tooling: backpressure from build, types, tests, pre-commit; the loop itself.
- Text: specs, a plan file, and the agent file as "signs".

### Warning
Against placeholder code: "DO NOT IMPLEMENT PLACEHOLDER OR SIMPLE IMPLEMENTATIONS." (2025-07-14)

---

## 7. Steve Yegge (steveyegge: beads, gastown)

### Stated principles
1. "Beads provides a persistent, structured memory for coding agents. It replaces messy markdown plans with a dependency-aware graph" (beads README) https://github.com/steveyegge/beads
2. The minimal agent-file section he recommends is 4 lines: "Run `bd prime` for workflow context", "Use `bd ready` ...", "Use `bd remember` ...", "Do not use markdown TODO lists for task tracking." (README)
3. Context comes from a command at session start (`bd prime` prints workflow context and memories), not from a long file.
4. "Compaction: Semantic 'memory decay' summarizes old closed tasks to save context window." (README)
5. Install integration with a command (`bd setup claude`, `bd setup codex`) that writes hooks and settings, not with copy-paste.
6. Gastown commit `0d7f5d1` "fix(priming): reduce AGENTS.md to bootstrap pointer" (2026-01-10) states the principle in a commit.

His Medium post "Introducing Beads" returned HTTP 403: not verified.

### Setup in beads
- `AGENTS.md` and `CLAUDE.md`: both 245 lines, 1,892 words (same content). Nested `cmd/bd/AGENTS.md`.
- `.claude/settings.json`: 2 PreToolUse hooks on Bash: `block-gh-watch.sh` and `block-interactive-cmds.sh`. The second blocks `cp`/`mv`/`rm` without `-f` because macOS aliases cause the agent to "hang indefinitely". It denies with a reason that tells the agent the fix.
- 5 git hooks in `.githooks/` (pre-commit, pre-push, post-checkout, post-merge, prepare-commit-msg). 1 skill.
- `bd doctor` detects "AGENTS.md / CLAUDE.md user-authored divergence" (commit `8694c53`, 2026-04-30): the tool checks the instruction files.

### Git history: beads `AGENTS.md`
- 125 commits. 1,528 words at the first commit ("migrated bootup instructions to AGENTS.md", 2025-10-15). Peak 5,548 words (2025-11-05). 4,142 words, then 19 words at `f3b0fb7` "refactor: consolidate agent instructions into CLAUDE.md" (2025-12-20). Now 1,892 words (2026-11-13). It grew back to +24% over the start.
- `83ae110` "refactor: Remove legacy MCP Agent Mail integration (bd-6gd)" (2025-12-18).
- `5528315` "Revert 'docs: forbid crew workers from creating PRs'" (2026-01-11): a text rule added and reverted the same day.
- `0773e63` "docs(agents): contributor-only agent instructions and documented-issue intake (#7223)" (2026-10-05).
- Gastown `AGENTS.md`: 9 commits; 216 -> 22 -> 43 ("bootstrap pointer", 2026-01-10) -> 906 now.

### Tooling versus text
- Tooling: the `bd` CLI as the work queue and memory, PreToolUse deny hooks, git hooks, `bd doctor`.
- Text: one file that keeps regrowing.

### Warning
"Do not use markdown TODO lists for task tracking." (README)

---

## 8a. Dex Horthy (HumanLayer)

### Stated principles (Advanced Context Engineering, about 2025-08; no date on page) https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/ace-fca.md
1. "a family of techniques I call 'frequent intentional compaction'"
2. A "research, plan, implement" workflow.
3. Research: "Understand the codebase, the files relevant to the issue, and how information flows"
4. Plan: "Outline the exact steps we'll take to fix the issue, and the files we'll need to edit and how"
5. "keeping utilization in the 40%-60% range"
6. "you build high-leverage human review into your pipeline."
7. "A bad line of code is... a bad line of code. But a bad line of a plan could lead to hundreds of bad lines of code."
8. From the HumanLayer blog (author Kyle, not Dex, 2025-11-25): "Frontier thinking LLMs can follow ~ 150-200 instructions with reasonable consistency", "< 300 lines is best, and shorter is even better", and "Never send an LLM to do a linter's job." https://www.humanlayer.dev/blog/writing-a-good-claude-md

### Setup in `humanlayer/humanlayer`
- `CLAUDE.md`: 278 lines, 2,228 words (AGENTS.md is a copy). Mostly commands. Check output is silent on success ("prints just '✓ quality passed' on success and shows output ONLY on failure").
- `.claude/hooks/`: 2 scripts. `stop-checks.sh` runs prebuild, quality and typecheck and exits 2 on failure (a Stop hook). `block-test-output-filtering.sh` blocks piping test output to head/tail/grep. The committed `.claude/settings.json` does not register them (it has 3 permission allows and env vars). Where they are wired: not verified.
- 29 entries in `.claude/skills` and `.claude/commands`, including research/plan/implement commands.

### Git history: `CLAUDE.md`
- 16 commits. 531 words (2025-05-23) -> 945 (2025-06-17) -> 449 (`6014ccf` "remove python/uv references from build and docs", 2025-09-30) -> 2,241 (`d8197ba`, 2026-10-22, monorepo merge) -> 2,228 now.
- `e599fa4` "Cleanup for make commands and ci (#213)" (2025-06-16).
- Grew 4.2x, mostly in one monorepo merge.

### Tooling versus text
- Tooling: silent check wrappers, Stop hook on typecheck, a hook that protects test output, slash commands for each phase.
- Text: commands and repo structure.

### Warning
Against reviewing only code: "When you review the research and the plans, you get more leverage than you do when you review the code."

---

## 8b. Harper Reed

### Stated principles
1. "Brainstorm spec, then plan a plan, then execute using LLM codegen. Discrete loops." (2025-02-16) https://harper.blog/2025/02/16/my-llm-codegen-workflow-atm/
2. Save the plan as `prompt_plan.md` and "output a `todo.md` that can be checked off." (same)
3. "The success really depends on how well step 2 went." (same)
4. Commit `ada6427` message (2026-07-16): "docs: scope agent rules by intent: kill incantations and blanket gates" (punctuation changed). https://github.com/harperreed/dotfiles/commits/main/.claude/CLAUDE.md
5. Commit `5519067` (2026-09-25): "revert(claude): drop the compaction-guard hook, keep the Now template".
6. Commit `9b7fbb2` (2026-10-15): "fix(agents): keep gotchas files small enough to read whole".

### Setup in `harperreed/dotfiles`
- Global `.claude/CLAUDE.md`: 180 lines, 3,299 words, 18 sections.
- `.claude/settings.json`: 1 hook (SessionStart). No permission lists. 3 commands. Many old skills moved to `.claude/skills-archive/`.

### Git history: `.claude/CLAUDE.md`
- 70 commits, 2025-04-30 to 2026-11-18. 644 words at the first commit, peak 4,449 (`2eba584` "docs: require focused review for high-risk changes", 2026-11-12), 2,789 the same day (`0f99133` "docs: tighten agent rules without changing requirements"), 3,299 now. It grew 5.1x.
- `d9855fb` "refactor: adopt simmer-refined global CLAUDE.md: cut filler, repair lying line" (2026-07-06): 1,855 -> 1,781.
- `bfe27bd` added a compaction-guard hook; `5519067` removed it the same day (2026-09-25).

### Tooling versus text
- Mostly text. One SessionStart hook. Plans and todo files as the work order.

### Warning
Being "over my skis": moving faster than he can check (2025-02-16).

---

## Synthesis

### Table

Always-loaded words = the root instruction file in the named repo, measured 2026-11-20. Hooks = Claude Code hooks committed in that repo.

| Person | Repo, file | Always-loaded words | Hooks (count) | Main enforcement layer | Sandbox or permission limits | Tests agent behaviour |
|---|---|---|---|---|---|---|
| Karpathy | autoresearch `program.md` | 1,140 | no (0) | fixed metric plus git reset | not stated | no (the metric tests the output) |
| Willison | llm `AGENTS.md` | 67 (datasette: 61) | no (0) | test suite in CI | yes, recommends sandboxes and budget-capped keys | no |
| Ronacher | agent-stuff `AGENTS.md` | 74 | no (0) | fast CLIs, skills, logs | Docker; permission checks off | no |
| Steinberger | agent-scripts `AGENTS.MD` (global) | 2,592 | no Claude hooks; 1 git pre-commit | skills plus PR CI | not stated (YOLO style implied) | yes, pre-commit validates skill files |
| Hashimoto | ghostty `AGENTS.md` | 225 (plus 9 nested, on demand) | no (0) | scripts, lint, CI, vouch | not stated | no |
| Huntley | overalls `AGENTS.md` | 1,684 | no Claude hooks; prek pre-commit | backpressure: build, types, tests | not stated | no |
| Yegge | beads `AGENTS.md`/`CLAUDE.md` | 1,892 | yes (2 PreToolUse) plus 5 git hooks | `bd` CLI, deny hooks | deny hooks only | partly: `bd doctor` checks instruction-file drift |
| Horthy | humanlayer `CLAUDE.md` | 2,228 | 2 hook scripts (registration not verified) | Stop hook typecheck, silent checks | 3 permission allows | no |
| Reed | dotfiles `.claude/CLAUDE.md` (global) | 3,299 | yes (1 SessionStart) | text | no | no |

### The 10 shared principles (ranked by how many say it)

1. Give the agent a way to verify its own work: tests, build, types, a metric. Willison, Hashimoto, Huntley, Karpathy, Steinberger, Ronacher, Horthy (Stop-hook typecheck).
2. Enforce with tools, not prose; a rule that a tool can check belongs in the tool. Hashimoto ("programmed tools"), Huntley ("back pressure"), Willison (prompt protection fails), HumanLayer ("Never send an LLM to do a linter's job"), Yegge (deny hooks).
3. Keep the always-loaded file short and factual: commands, layout, gotchas. Willison (67 words), Ronacher (74), Hashimoto (225), Yegge ("bootstrap pointer"), HumanLayer (<300 lines).
4. Each rule comes from a real observed mistake. Hashimoto ("each line ... a bad agent behavior"), Steinberger ("organizational scar tissue"), Willison (datasette alert rule), Huntley ("signs"), Yegge (cp/mv/rm hook comment).
5. CLIs and scripts over MCP; load capability on demand (skills). Ronacher, Steinberger, Willison, Yegge (`bd` CLI).
6. Small scope per step: one task per loop, one file in scope, small diffs. Huntley ("one thing per loop"), Karpathy ("leash", one editable file), Horthy (plan steps), Reed (discrete loops).
7. Spec or plan first, kept as a file or tracker, not in chat. Huntley (specs, fix_plan.md), Reed (prompt_plan.md, todo.md), Horthy (research, plan), Yegge (beads graph).
8. Contain the blast radius: sandbox, scoped credentials, Docker. Willison, Ronacher, Karpathy (exfiltration warning).
9. Manage context deliberately: compact, keep tool output quiet, load docs on demand. Horthy (40-60%), Ronacher (fast tools, little output), Karpathy (redirect output to a log), Yegge (memory decay), HumanLayer (progressive disclosure).
10. The human stays the reviewer and owner of what ships. Willison (no unreviewed PRs), Hashimoto (AI policy), Horthy (review plans).

### Disagreements
- Long versus short files: Willison, Ronacher and Hashimoto keep 60 to 230 words. Steinberger (2,592), Reed (3,299), Horthy (2,228) and Yegge (1,892) run large global or monorepo files. Steinberger and Yegge cut hard (to 397 and 19 words) and then regrew above the start. Nobody with a long file shows a measured follow rate.
- Hooks: Yegge and HumanLayer use deny and Stop hooks. Steinberger says models get around hooks if determined and relies on CLIs, shims and CI. Reed added a hook and reverted it the same day.
- Permissions: Ronacher disables all permission checks and uses Docker. Willison insists on a sandbox and budget-limited keys. Steinberger runs many agents in one folder with atomic commits as the safety.
- Many agents versus one: Steinberger (3 to 8 parallel), Huntley (concurrent agents with a message board), Yegge (gastown swarms) versus Karpathy (one autonomous loop) and Hashimoto (one or more background agents, no notifications).
- Plan mode and subagents: Steinberger calls plan mode "a hack" and subagents "charade". Horthy builds his whole method on research and plan phases, often with subagents.
- MCP: Ronacher, Steinberger, Willison against most MCP; HumanLayer itself started as an approvals MCP (commit `6ed9301` "approvals mcp", 2025-05-27).

### Applicability to the target setup

Target: one owner, Claude Code and Codex, a personal setup repo. It installs a 3,200-word always-loaded rules file (83 instructions), a 38-rule table (27 are hook-injected reminder text, measured 75% not followed), and a 5,600-line Python hook router with 11 command gates. Goal: small, generic, plug-and-play, rules that hold in every session.

Ranked by expected effect:

1. Delete the 27 reminder-text rules and do not re-inject them. Keep a rule only if a tool can enforce it or a real mistake shows the agent needs it. Source: Willison, lethal trifecta (prompt protection is not dependable); the target's own 75% miss rate. Cheap (hours).
2. Turn each surviving "must" into a check that fails: lint, test, pre-commit or CI. Examples: the em-dash rule becomes a lint in `make check-fast`; the PR-body rule becomes a CI check on the PR. Source: Hashimoto, harness engineering (2026-02-05); HumanLayer "Never send an LLM to do a linter's job". Medium (days).
3. Cut the always-loaded file to under about 300 words: the check commands, the layout pointer, and the 5 to 10 safety rules with reasons. Move the rest into skills and nested files that load on demand. Source: Hashimoto (225 words plus 9 nested files); Willison (67); HumanLayer (<300 lines, ~150-200 instruction budget, and Claude Code's own prompt uses ~50). Cheap to medium.
4. Make the agent's own loop end in verification: a Stop hook (or the Codex equivalent) that runs `make check-fast` and returns the failure text. This replaces many "before done" reminders. Source: HumanLayer `stop-checks.sh`; Willison "First run the tests". Cheap.
5. Keep hooks only as hard denies with a fix in the reason, for a few destructive or hang-prone commands (push to main, `--no-verify`, secrets, interactive commands). Source: Yegge, beads `block-interactive-cmds.sh` (deny plus "Use `cp -f`"). Medium: shrink the 5,600-line router to a few small scripts.
6. Move safety to the sandbox and credential layer, not to rules: run agents in a container or with OS sandbox and permission deny lists; give only staging or budget-capped keys. Source: Willison (2025-09-30); Ronacher (Docker). Medium.
7. Write a new rule only after an observed failure, with the failure in the commit message, and review the file on a schedule to delete rules that no longer fire. Source: Hashimoto ("each line ... a bad agent behavior"); Steinberger's two cuts ("cut tokens", "trim agent instructions"). Cheap.
8. Replace text workflow (branch, ticket, PR order) with a CLI that holds state and prints the next step, injected at session start in a few lines. Source: Yegge, `bd prime` and the 4-line AGENTS.md section; gastown "reduce AGENTS.md to bootstrap pointer". Large.
9. Prefer CLIs and skills over MCP servers that load at every session, to free context. Source: Ronacher (2025-07-03); Steinberger ("Almost all MCPs really should be clis"); Willison (skills cost "a few dozen extra tokens"). Cheap to medium.
10. Make check output quiet on success and full on failure, and block piping test output through head or grep. Source: HumanLayer CLAUDE.md and `block-test-output-filtering.sh`; Ronacher ("less useless output"); Karpathy (redirect to log). Cheap.
11. Use one spec or plan file per task with one item per agent loop, instead of a routing table that tries to cover every case. Source: Huntley, Ralph (2025-07-14); Horthy, research-plan-implement; Reed (`prompt_plan.md`). Medium.
12. Measure follow rate per rule before and after each change, with a few fixed scripted tasks run in `claude -p` and `codex exec`; keep rules that move the number. None of the 9 people publishes such a test, so this fills a gap. Partial precedent: Yegge's `bd doctor` drift check, Steinberger's skill validation in pre-commit, Karpathy's single fixed metric. Medium.

Expected size after 1 to 5: an always-loaded file of about 200 to 300 words, a few hard-deny hooks, a Stop-hook check, and CI checks. This matches Hashimoto, Willison and Ronacher, who have the shortest files and the strongest tool layer.

### Could not confirm
- Karpathy's X post of 2026-01-26: HTTP 402. Quotes come from Osmani (2026-01-28) and other secondary write-ups.
- Karpathy "keep the AI on a leash": only from secondary summaries of the June 2025 talk.
- Huntley's "stdlib" content: paywalled after the intro.
- Yegge's Medium "Introducing Beads": HTTP 403.
- Where HumanLayer wires `stop-checks.sh` and `block-test-output-filtering.sh`: not in the committed `.claude/settings.json`.
- Exact publish dates of steipete's two posts and of Willison's guide chapters: not shown on the pages; dates are estimates from references.
- Whether any of these people measures the rate at which agents follow rules: I found no published measurement.
- The claim that Karpathy joined Anthropic (one marketing blog): not confirmed, not used.
- Thorsten Ball: essay only (2025-04-15, "It's not that hard to build a fully functioning, code-editing agent." https://ampcode.com/how-to-build-an-agent); no instruction file studied.
