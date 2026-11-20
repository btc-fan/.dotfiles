# I. Plugins, extensions and overlaps: a read-only audit (2026-11-20)

Machine: the main Mac, user <user>. Claude Code 2.1.325, Codex 0.170.0 (codex-cli), oh-my-codex 0.22.11.
Project used for the per-project view: <project-a>.
Setup state read: `origin/ai` at 1aafab6 (2026-11-20 17:15, "feat(gate): ask-first"). The local checkout is on `ai` at 443536f (2026-11-20 11:26).

## 0. Method and the main measurement source

- The best measure of "what a session really loads" is the transcript of the parent session:
  `~/.claude/projects/-Users-<user>-work-<project-a>/b04199a0-d8d7-4317-ac23-8a0b44e3e0a6.jsonl`.
  Its attachments hold the real text of each SessionStart hook, the skill listing, the agent listing, the MCP server instructions, the deferred tool names and the loaded instruction files. All "words" numbers below come from that file, unless a row says "source count" or "estimate".
- I did not run a hook. The ai-core router and the OMC hooks write state, so they are not pure prints.
- A second transcript (`690a8739-...jsonl`, a long session of 2026-11-18, 646 Bash calls) gives the per-call text that hooks add.
- Usage counts come from a search over all 203 project folders in `~/.claude/projects` (tool_use records and typed `<command-name>` records).
- Tokens = words x 1.4, as asked. Deferred tool names are not prose: for them I give characters / 4.
- No secret value is printed here. One finding: `ai/marketplace/plugins/ai-core/mcp/context7.sh` holds a committed default context7 key (owner-approved, SPEC 13). I saw it while I read the launcher. I do not repeat it.

## 1. Inventory: what loads in a new Claude session today

### 1.1 Plugins (from `~/.claude/plugins/installed_plugins.json` and `enabledPlugins`)

| Plugin | Version | Installed by | User scope | Project scope (<project-a>) | Loads here |
|---|---|---|---|---|---|
| ai-core@ai | 1.0.0 (local marketplace `~/.dotfiles-ai/ai/marketplace`) | setup (install.sh) | true | - | yes |
| ai-serena@ai | 1.0.0 | setup | true | - | yes |
| ai-playwright@ai | 1.0.0 | setup | false | - | no |
| ponytail@ponytail | 5.3.3 (local marketplace `~/.local/share/ai/plugins/ponytail`) | setup | true | - | yes |
| i-have-adhd@i-have-adhd | 0.4.1 (local marketplace) | setup | true | - | yes |
| oh-my-claudecode@omc | 5.8.5 (GitHub ref v5.8.5) | setup | true | - | yes |
| ui-ux-pro-max@ui-ux-pro-max-skill | 2.13.0 in the manifest (the rule file says v2.15.0 = a38d04c) | setup | false | true | yes (here and in <project-b>) |
| claude-seo@agricidaniel-claude-seo | 2.6.2 | setup | false | - | no (no project enables it) |
| claude-blog@agricidaniel-blog | 2.3.2 | setup | false | - | no (no project enables it) |
| typesafe@typesafe-ai | 0.5.7 | owner by hand (in `AI_OFF_CLAUDE_PLUGINS`) | false | - | no |

Not installed although `ai/pins.env` says "Claude plugin, on by default": last30days (`LAST30DAYS_SOURCE`). Not found in `installed_plugins.json`.

### 1.2 Other sources

| Source | Where | Installed by |
|---|---|---|
| User skills | `~/.claude/skills`: 999-ads, omc-reference (owner, real folders); ask-matt, grill-me, grilling, retro, wait-what, writing-for-agents (Matt links); create-verification-skill, maintain-verification-skill (pstack links); promote-skill, release, setup-rollout, ship, skills-guide, upgrade-review (setup links to `~/.dotfiles-ai/ai/skills`); `synced/` (claude.ai org skills); `.trash/` | setup + owner |
| Codex/agents skills | `~/.agents/skills`: same links as above plus prompting-claude-and-codex | setup |
| Project skills | `<project-a>/.claude/skills`: 15 Matt links (code-review, codebase-design, diagnosing-bugs, domain-modeling, grill-with-docs, handoff, implement, improve-codebase-architecture, pr, prototype, research, tdd, to-spec, to-tickets, wayfinder) and an `.omc/` folder | ai-adopt |
| User agent | `~/.claude/agents/json-aberration-analyzer.md` | owner, old |
| User hooks (settings.json) | herdr session-note, herdr-agent-state, herdr ask-hook (PermissionRequest), rtk-hook (PreToolUse Bash) | setup + herdr |
| Leftover hook files | `~/.claude/hooks/caveman-*.js` (not wired in settings.json) | old caveman install |
| statusLine | OMC HUD (`~/.claude/hud/omc-hud.mjs`) | OMC setup |
| claude.ai connectors | 38 servers, 228 deferred tool names in total with the others | claude.ai account |
| Bundled Claude Code skills | dataviz, artifact-*, update-config, keybindings-help, simplify, fewer-permission-prompts, loop, schedule, claude-api, workflow-authoring, run, plugin-authoring, init, security-review | Claude Code |
| CLI tools | graphify 0.9.112, rtk 1.2.0, herdr 0.9.5, serena 2.1.0 | setup |

## 2. One section per extension

Format for each: (1) what and where, (2) fixed cost per session, (3) per prompt and per tool call, (4) overlaps and conflicts, (5) switches, (6) verdict, (7) layer.

### 2.1 ai-core (the setup's own plugin)

1. Hook router, gates, stop check, notifier, rtk wrapper, context7 MCP and 1 skill (prompting-claude-and-codex). Version 1.0.0. Cache: `~/.claude/plugins/cache/ai/ai-core/1.0.0` (a copy, not a link). Source: `~/.dotfiles-ai/ai/marketplace/plugins/ai-core`. Installed by install.sh. Codex: same plugin, `hooks/codex-hooks.json` (11 commands).
2. Fixed cost:
   - SessionStart text: 137 words (upgrade-review note, skill card, author-sessions line). Measured.
   - Skill descriptions: 1 skill, 54 words.
   - MCP: context7, 2 deferred tools, 110 words of server instructions.
   - Hook commands (Claude, cache manifest): SessionStart 3 (router 10 s, stop-check 10 s, caffeinate 5 s), UserPromptSubmit 1 (30 s), UserPromptExpansion 1 (30 s), PreToolUse 1 (90 s, matcher `Bash|Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob|Agent|Task|Skill`), PostToolUse 1 (10 s), Stop 2 (60 s, 60 s), SubagentStop 1 (60 s), SessionEnd 2 (serena cleanup 10 s, router 5 s). Total 12.
   - The rtk wrapper is in the user `settings.json`, not in the plugin (PreToolUse Bash, no timeout, path into the checkout `~/.dotfiles-ai/ai/marketplace/plugins/ai-core/hooks/rtk-hook`).
3. Per prompt and per call:
   - L2 forced-eval checklist on a matched prompt: "[ai router L2] Before you act, answer YES or NO for each item ..." 86 to 115 words per firing (6 firings, 516 words in this session; 16 firings, 1,833 words in session 690a8739).
   - "[ai router: sessions]" line again on some PreToolUse calls (21 times, 501 words in 690a8739).
   - Nudges after a write: no-em-dash, ste-sentence. Note: the no-em-dash nudge fired on a scratch file that held copied third-party text.
   - Gates (PreToolUse deny): secret-scan, pr-rules, merge-approval, no-verify, writing-for-agents, ship, gh-write, ask-first (new today), winner-gate, nav-first, audit-before-install, verify-tool-*, pr-url.
4. Overlaps and conflicts:
   - Stale cache. `origin/ai` narrowed the PreToolUse matcher to `Bash|Edit|Write|MultiEdit|NotebookEdit|Grep|Skill` and added `"onFailure": "block"`. The installed cache still has the old wide matcher and no onFailure. The plugin version stays "1.0.0", so Claude Code has no version change to pick up. `router.py` and `hooklib.py` in the cache differ from both the checkout and origin (sha1 prefixes: cache 20fa78ec38, checkout 07d0a0dcee, origin 7543734ad1 for router.py).
   - Winner gate overlaps with OMC skill names (section 2.5). It is the only working silencer for OMC skills, because `skillOverrides` does not act on third-party plugin skills (section 2.5, point 4).
   - Stop: 2 ai-core Stop hooks plus 5 OMC Stop hooks (section 2.5).
   - The `ai-serena` hook `serena-hook cleanup` runs at Claude SessionEnd, but Claude SessionStart has no `activate` (Codex has both).
5. Switches: `.ai/enabled` lines (`no-serena`, `no-graph`, `no-ui`, `no-stop-check`); owner gate skip `sudo ai-gate-skip <gate> <minutes> <why>`; `enabledPlugins."ai-core@ai": false` (any scope; a project can set it, see F); `disableAllHooks`.
6. Verdict: KEEP-WITH-CONFIG. Install the origin manifest and bump `version` in `.claude-plugin/plugin.json` on each hook change, so the cache refreshes. Cut the L2 checklist and the repeated sessions line (plan Phase 1). Cut the session-start card to one status line under 60 words (plan 6.9).
7. Layers: gates = L3; stop-check = L4; skill card = L5 (one line); context7 and the skill = L6.

### 2.2 ai-serena / Serena

1. Serena 2.1.0 MCP server (`serena start-mcp-server --project-from-cwd --context=claude-code`). Plugin `ai-serena@ai` 1.0.0, enabled at user scope. Installed by the setup. Codex: `mcp_servers.serena` in `~/.codex/config.toml` with `--context=codex`.
2. Fixed cost:
   - 14 tools load up front with full schemas (they are not deferred; I see them in my own tool list): find_declaration, find_implementations, find_referencing_symbols, find_symbol, get_diagnostics_for_file, get_symbols_overview, initial_instructions, insert_after_symbol, insert_before_symbol, rename_symbol, replace_content, replace_in_files, replace_symbol_body, safe_delete_symbol. Estimate from the schemas in my context: about 2,100 words.
   - Server instructions: 21 words ("CRITICAL: Before starting to work on a coding task, call the `initial_instructions` tool ...").
   - `~/.serena/serena_config.yml`: `excluded_tools: [execute_shell_command, serena_repl]`. No memory tools are exposed in this session.
3. Per call: nothing injected by hooks. ai-core PostToolUse matches `mcp__.*serena.*`.
4. Overlaps and conflicts:
   - Navigation, 3 voices (verified): the global rules say "graphify query first, then Serena"; Serena says "CRITICAL ... call initial_instructions"; OMC says "Consider using Grep" (post-tool-verifier.mjs:1131) and its explore agent says "For files >500 lines, ALWAYS use `lsp_document_symbols` instead of Read" (agents/explore.md:48).
   - OMC `t` server offers 12 `lsp_*` tools and 2 `ast_grep_*` tools (deferred) for the same job.
   - The plugin description says "opt-in per project", but the plugin is on at user scope and `ai/rules/serena.md` says "On by default in every project". The description is stale.
   - Serena writes `.serena/` into each project and adds each project to `projects:` in `~/.serena/serena_config.yml` (many eval repos are listed).
   - Use (all transcripts): find_symbol 20, find_referencing_symbols 17, get_symbols_overview 10, initial_instructions 2, insert_before_symbol 1. The other 9 tools: 0 calls.
5. Switches: `excluded_tools` in `~/.serena/serena_config.yml` (global) or `.serena/project.yml` (project); `--context` / `--mode` arguments in the plugin `.mcp.json`; `.ai/enabled` `no-serena`; `enabledPlugins."ai-serena@ai": false`.
6. Verdict: KEEP-WITH-CONFIG. Add to `excluded_tools` in `~/.serena/serena_config.yml`: `find_declaration, find_implementations, get_diagnostics_for_file, insert_after_symbol, replace_content, replace_in_files, safe_delete_symbol, initial_instructions`. Keep find_symbol, find_referencing_symbols, get_symbols_overview, replace_symbol_body, rename_symbol, insert_before_symbol. Estimate: removes about 1,200 words per session and the "CRITICAL" voice. Fix the stale plugin description.
7. Layer: L6 (MCP on demand). Its one-line use rule: L5 index.

### 2.3 ponytail

1. "Lazy senior dev" coding and reply mode. 5.3.3, `~/.claude/plugins/cache/ponytail/ponytail/5.3.3`, local marketplace `~/.local/share/ai/plugins/ponytail`. Installed by the setup. Also enabled in Codex (`<email> = true`).
2. Fixed cost:
   - SessionStart text: 493 words (2,859 characters). Measured.
   - SubagentStart: the same ruleset again into each subagent (verified: this subagent received it). The owner ran about 480 Agent calls in all transcripts.
   - Skills: 6 (ponytail, -audit, -debt, -gain, -help, -review), 253 words. Commands: 6 TOML files.
   - Hooks: SessionStart 1 (15 s), SubagentStart 1 (15 s), UserPromptSubmit 1 (15 s, mode tracker). Plus a hooks module `band/register.tsx` (the band above the prompt).
3. Per prompt: the tracker writes text only on a `/ponytail` command or "stop ponytail". No text on ordinary prompts.
4. Overlaps and conflicts:
   - Reply shape: "End your reply with one or two lines: what you skipped or did not check, and any risk the user must know." See section D.
   - Same job as OMC `minimal-code-discipline` ("YAGNI-ladder ... existence-first, reuse before writing, dependency ladder, shortest correct diff") and OMC `ai-slop-cleaner`. Same job as `ponytail-review` versus Matt `code-review` and OMC `review`.
   - Personal files: writes `~/.config/ponytail/config.json` on a default change, and the task ledger `~/.config/ponytail/band/<project>.csv` after each turn (option `ledger`, default true). The band folder has 10+ CSV files and `board.html`.
   - Use: 0 Skill calls to `ponytail:*` in all transcripts. The value is the injected ruleset, not the skills.
5. Switches: `PONYTAIL_DEFAULT_MODE=off|lite|full|ultra` (env, wins) or `defaultMode` in `~/.config/ponytail/config.json` (now "full"). Mode "off" stops both the SessionStart and the SubagentStart injection. `PONYTAIL_QUIET_STARTUP`, `PONYTAIL_HIDE_STATUS` (banner only). Plugin options (`userConfig`): `ledger`, `webhookUrl`, `webhookToken`, `sendNames` (set through the plugin configure UI; stored per plugin in settings; exact stored key not verified).
6. Verdict: KEEP-WITH-CONFIG. Keep `full` in the main session (the owner likes it, and its closing line is part of the owner's intent). Set plugin option `ledger` to false if the owner does not use the board. Let the single reply-style source (section D) own the closing line, so ponytail's line and the style do not fight.
7. Layer: coding discipline = L5 text (injected); review/audit skills = L6.

### 2.4 i-have-adhd

1. Reply shaping for an ADHD reader. 0.4.1, `~/.claude/plugins/cache/i-have-adhd/i-have-adhd/0.4.1`. Installed by the setup. Also enabled in Codex.
2. Fixed cost: SessionStart text 1,215 words (6,989 characters), the full SKILL.md, printed because the flag file `~/.claude/.i-have-adhd-always` exists (0 bytes, created by the setup or the owner). Skill: 1, `disable-model-invocation: true`, so 0 words in the listing. Hooks: SessionStart 1 (30 s).
3. Per prompt and call: nothing.
4. Overlaps and conflicts: see section D. It repeats the global rules (lead with the action, numbered steps, no recap) and contradicts ponytail on the last line.
5. Switches: delete `~/.claude/.i-have-adhd-always` (stops the always-on print; `/i-have-adhd` still works as a typed skill); "stop adhd mode" per session; `enabledPlugins."i-have-adhd@i-have-adhd": false`.
6. Verdict: REPLACE-OVERLAP. The single reply-style source wins (section D). Silence: delete the flag file. Keep the plugin installed and typed-only.
7. Layer: L5 through the output style; the plugin itself stays L6 (typed `/i-have-adhd`).

### 2.5 oh-my-claudecode (OMC)

1. Multi-agent orchestration. 5.8.5, `~/.claude/plugins/cache/omc/oh-my-claudecode/5.8.5`, marketplace GitHub `Yeachan-Heo/oh-my-claudecode` ref v5.8.5. Installed by the setup (macOS: on everywhere; servers: off by default per `ai/rules/omc.md`).
2. Fixed cost:
   - Skills: 84 skill folders in the manifest, 76 entries in the listing, 1,558 words (the listing budget cut many OMC entries to the name only; their full descriptions are 2,275 words).
   - Agents: 19, 305 words in the agent listing.
   - MCP: server `t`, 50 deferred tools (notepad, state, wiki, project_memory, lsp, ast_grep, python_repl, trace, session_search), names only up front.
   - Commands: 21.
   - SessionStart text: 15 words in this session (`<project-memory-context>` with "C/C++" and hot paths). The project memory block can grow (235 words over 4 starts in session 690a8739).
   - Hook commands: 31, plus the hooks module `jev-compaction.mjs`. Per event: UserPromptSubmit 2 (keyword-detector 30 s, skill-injector 30 s); SessionStart 5 (5 s each) + 2 conditional (init 30 s, maintenance 60 s); PreToolUse 2 (pre-tool-enforcer `*` 60 s, git-guardrails Bash 5 s); PermissionRequest 1 (Bash 5 s); PostToolUse 4 (post-tool-verifier `*` 10 s, project-memory-posttool `*` 3 s, rules-injector R/W/E 3 s, directory-context-injector R/W/E 3 s); PostToolUseFailure 1 (3 s); SubagentStart 1 (3 s); SubagentStop 2 (5 s, 5 s); PreCompact 3 (10, 5, 3 s); Stop 5 (context-guard 5 s, workflow-drift-guard 3 s, persistent-mode 20 s, budget-guard 5 s, code-simplifier 10 s); SessionEnd 2 (30 s, 30 s).
3. Per prompt and per call (measured in transcripts):
   - PreToolUse Bash: "Use parallel execution for independent tasks. Use run_in_background for long operations ..." 15 words each (80 times, 1,200 words in session 690a8739).
   - PreToolUse Agent: "Spawning agent: <type> (<model>) | Task: ..." about 13 words each.
   - PreToolUse Edit: "Verify changes work after editing ..." 10 words; Read: "Read multiple files in parallel ..." 10 words.
   - PostToolUse: "File written. Test the changes ...", "Code modified. Verify ...", "Background operation detected ...", "Extensive reading (N files). Consider using Grep ...", a context warning at 70 percent (`PREEMPTIVE_WARNING_THRESHOLD_PERCENT` 70).
   - PostToolUseFailure: "Tool \"Bash\" failed. Analyze the error, fix the issue, and continue working." 12 words each.
   - PostToolUse Read/Edit: the nearest README.md and AGENTS.md, up to 5,000 tokens each, once per file per session (the project AGENTS.md came in again: 377 words, although CLAUDE.md already loads it).
   - Rules injector: `.claude/rules`, `.github/instructions`, `.cursor/rules`, `~/.claude/rules` on file access.
   - "[SLOP WARNING]" on fallback words in a tool input; "The boulder never stops" in persistent modes.
   - "[MAGIC KEYWORD: AUTOPILOT]" was injected once on 2026-11-18 (session 690a8739), from keyword-detector. Today `OMC_SKIP_HOOKS=keyword-detector` is set; I saw no such line today.
   - Denies: read budget (a full Read of a big file: warn once, then deny; `OMC_READ_BUDGET=off`), force agent delegation (config), git-guardrails (only in unattended modes or `OMC_GIT_GUARDRAILS=1`).
   - PermissionRequest: auto-allows Bash commands that it thinks are safe and read-only (`dist/hooks/permission-handler/index.js:423`), when no `ask` rule matches.
4. Overlaps and conflicts (each claim of audit 2026-11-18 section 6 checked again):
   - Claim 1, walls: VERIFIED. Read budget deny (`pre-tool-enforcer.mjs` around line 2525). Workflow drift guard blocks a Stop on an option question that should be AskUserQuestion, and on a "done" claim with TODO/stub/skipped tests (`workflow-drift-guard.mjs:921`, `:930`). Context guard: default 75 percent; `OMC_CONTEXT_GUARD_THRESHOLD=94` is set; at 95 percent or more it lets the stop through (`CRITICAL_THRESHOLD`), so it blocks only from 94 to 94.9 percent, at most 2 times (`MAX_BLOCKS = 2`).
   - Claim 2, many Stop blockers: PARTLY TRUE. 7 Stop commands run. Today 5 can block: ai-core stop-check, OMC context-guard, workflow-drift-guard, persistent-mode (only in an active mode). The router has no `strength: stop` rule since 2026-11-18. budget-guard defaults to `OMC_BUDGET_ENFORCE=shadow` (never blocks). code-simplifier is opt-in (`codeSimplifier.enabled` in the global OMC config.json; no such file exists). The `stop-check.py` comment "OMC itself never blocks when stop_hook_active is set" is false for context-guard-stop (no `stop_hook_active` check) and for code-simplifier (off). workflow-drift-guard, budget-guard and persistent-mode do check it.
   - Claim 3, memory: VERIFIED. `.omc/project-memory.json` in <project-a>; injected at each start ("C/C++"). `project-memory-session.mjs` does not read `OMC_SKIP_HOOKS`. No switch except `DISABLE_OMC=1` or plugin off. The owner rule says "No Serena memories, no Claude auto memory": OMC memory is a third memory against that rule.
   - Claim 4, personal file: VERIFIED and worse than stated. `post-tool-verifier.mjs:301-314` appends each agent Bash command to `~/.bash_history`. The file is 20,052,683 bytes and was written at 17:20 today. Switch: `"bashHistory": false` in `~/.claude/.omc-config.json` (the file exists, the key is absent, default = on). Risk: a token in a command line ends up in a shell history file.
   - Claim 5, text on each call: VERIFIED, plus 6 more strings (listed above). `OMC_QUIET` is not set.
   - Claim 6, duplicate AGENTS.md: VERIFIED (`DEFAULT_MAX_README_TOKENS = 5000`, the walk includes the working directory).
   - Claim 7, navigation voices: VERIFIED (quotes in 2.2).
   - Claim 8, skill names: VERIFIED and the cause is now known. The listing has 137 entries, 30,894 characters. `oh-my-claudecode:create-verification-skill`, `maintain-verification-skill`, `release` (user scope) and `pr`, `research`, `tdd` (project scope) are all still in the listing. Claude Code 2.1.325 code: for a skill with `source === "plugin"`, `dFe()` calls `JNt()`, which looks only at names of Anthropic-synced plugins (`Lln()` returns [] for another repository). So `skillOverrides` has no effect on any third-party plugin skill. The 6 entries are dead config. The winner gate is the only silencer that works for the Skill tool. A typed `/name` always runs.
   - Claim 9, reply shape: VERIFIED (numbers in section D).
   - Claim 10, keyword switch: VERIFIED. The worker still starts each prompt (run.cjs); skill-injector still runs. The 70 percent context nag is real (post-tool-verifier.mjs:185) and is silenced by the `post-tool-use` token.
   - Same names as the setup's skills: pr, research, tdd, release, create-verification-skill, maintain-verification-skill (6). Same jobs: plan/ralplan (Matt to-spec), execute (Matt implement), review (Matt code-review), wiki/remember/project memory (repo docs), verify (pstack + stop-check), deep-interview (Matt grilling), debug/trace (Matt diagnosing-bugs), external-context (context7), designer (ui-ux-pro-max), configure-notifications (herdr), git-master/babysit/fix-ci (setup git flow).
   - Files written: `.omc/` in each project (<project-a> has `.omc/project-memory.json`, `sessions/`, `state/`, and `.claude/skills/.omc/`), `~/.omc/` (state, sessions, project-memory.json, mcp-registry.json), `~/.claude/.omc-config.json`, `~/.claude/hud/`, `~/.bash_history`, symlinks in its own plugin cache (session-start.mjs about line 1800).
   - Use (all transcripts): OMC skills: only `oh-my-claudecode:cancel` (7 calls). OMC agents: executor 88, code-reviewer 74, security-reviewer 16, architect 15, critic 11, verifier 4, qa-tester 4. OMC `t` tools: 12 calls (state tools, from cancel). The agents carry the value.
5. Switches (all verified in code): `OMC_SKIP_HOOKS` tokens `keyword-detector`, `skill-injector`, `pre-tool-use`, `post-tool-use` (verifier, rules injector, dir-context injector, project-memory-posttool), `post-tool-use-failure`, `project-memory-posttool`, `subagent-tracker`, `workflow-drift-guard`, `persistent-mode`, `stop-continuation`; `DISABLE_OMC=1` (all hooks that honor it return early); `OMC_QUIET` (integer); `OMC_READ_BUDGET=off`; `OMC_GIT_GUARDRAILS=0|1`; `OMC_CONTEXT_GUARD_THRESHOLD`; `OMC_BUDGET_ENFORCE=off|shadow|active`; `OMC_SESSION_START_CONTEXT_BUDGET`; `bashHistory` in `~/.claude/.omc-config.json`. No switch: session-start, project-memory-session, wiki-session-start, stale-run-reporter, runs-reconciler, context-guard-stop, budget-guard, permission-handler, the skill listing, the agent listing. `enabledPlugins."oh-my-claudecode@omc"` at user or project scope removes all.
6. Verdict: KEEP-WITH-CONFIG on this Mac (the agents are in real use). Set `OMC_SKIP_HOOKS=keyword-detector,skill-injector,pre-tool-use,post-tool-use,post-tool-use-failure,project-memory-posttool` and `OMC_QUIET=2` in `~/.claude/settings.json` `env`; set `"bashHistory": false` in `~/.claude/.omc-config.json`; delete the 6 dead `skillOverrides` entries and put the losers in the routing.yaml `winners` table instead. Result: no per-call text, no AGENTS.md re-injection, no shell history writes. What stays: 1,558 words of skill listing, 305 words of agents, project memory at start, 5 SessionStart and 5 Stop processes. A second step for the owner (D6): OMC on per project only (`ai-adopt --tools omc`, as on servers). Then the agents leave too, so only do it if the owner accepts typed `/oh-my-claudecode:*` only in OMC projects.
7. Layers: agents and skills = L6; context guard = L4 (it is a self-check); git-guardrails, read budget = L3 (only if kept); the per-call reminders = none (remove).

### 2.6 oh-my-codex (OMX)

1. Codex orchestration. oh-my-codex 0.22.11 (npm global, `/opt/homebrew/lib/node_modules/oh-my-codex`). Installed by the setup (`OMX_SOURCE`).
2. Fixed cost in a Codex session:
   - `~/.codex/AGENTS.md`: 6,629 words. Lines 1 to 256 (OMX): 3,380 words. Lines 257 to 455 (`AI:core v1` block of the setup): 3,216 words. Rest 33.
   - `developer_instructions` in `~/.codex/config.toml`: 144 words ("You have oh-my-codex installed. AGENTS.md is the orchestration brain ...").
   - Skills in `~/.codex/skills`: 24; prompts in `~/.codex/prompts`: 33 role files.
   - Hooks in `~/.codex/hooks.json`: OMX `codex-native-hook.js` on SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, PostCompact, Stop (30 s), SubagentStop (7 commands, most without a timeout); `notify` = OMX notify-hook.
3. Per call: the OMX native hook runs on each tool call. Text not measured (not checked).
4. Conflicts:
   - `~/.codex/AGENTS.md` line 1 to 6, quote: "YOU ARE AN AUTONOMOUS CODING AGENT. EXECUTE TASKS TO COMPLETION WITHOUT ASKING FOR PERMISSION. DO NOT STOP TO ASK \"SHOULD I PROCEED?\" ..." The setup merged the `ask-first` gate today ("agents ask before high-impact steps": restart, boot, deploy, kill, delete). The global rules also say "Never deploy to production ... without my explicit OK". Direct contradiction in Codex.
   - OMX plan/ralplan, code-review, wiki, best-practice-research are already losers in the winner gate.
5. Switches: `OMX_AUTO_UPDATE=0`, `OMX_NATIVE_AUTO_FETCH=0` (set); the OMX block markers `<!-- OMX:... -->` in AGENTS.md; `developer_instructions` key. A documented OMX switch for the autonomy directive: not checked.
6. Verdict: KEEP-WITH-CONFIG. Remove or neutralize the AUTONOMY DIRECTIVE block when ai-sync renders `~/.codex/AGENTS.md` (it is a marked block), and cut the OMX part toward the plan's 600-word target. Mark the switch as unverified until the OMX docs are read.
7. Layers: OMX skills and roles = L6; the autonomy text = remove; the setup block = L5.

### 2.7 ui-ux-pro-max

1. UI design skills. Manifest 2.13.0 (rule says audited v2.15.0). `~/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.13.0`. Off at user scope, on in <project-a> and <project-b> project settings. Installed by the setup.
2. Fixed cost where on: 7 skills, 339 words in the listing (source count 325). No hooks, no agents, no MCP. The plugin `CLAUDE.md` (5.4K) is not loaded (Claude Code loads no plugin CLAUDE.md).
3. Per call: nothing.
4. Overlaps: OMC designer agent, OMC loft and visual-verdict, Matt prototype, bundled artifact-design. The routing rule "ui" points to ui-ux-pro-max.
5. Switches: `enabledPlugins."ui-ux-pro-max@ui-ux-pro-max-skill"` per project; `.ai/enabled` `no-ui`.
6. Verdict: KEEP-ON-DEMAND-ONLY (already applied). Note: `<project-a>` has no UI code yet ("no code yet" in its Map), so the 339 words are paid for nothing there today.
7. Layer: L6.

### 2.8 claude-seo

1. SEO suite. 2.6.2, `~/.claude/plugins/cache/agricidaniel-claude-seo/claude-seo/2.6.2`. Off at user scope; no project enables it.
2. Cost if on: 29 skills, 1,252 words (source count); 20 agents, 497 words; 1 PostToolUse `Edit|Write` hook (30 s, schema validation).
3. Per call when on: the PostToolUse hook.
4. Overlap: claude-blog (tie-break rules in routing.yaml), OMC none.
5. Switches: `enabledPlugins."claude-seo@agricidaniel-claude-seo"` per project (`ai-adopt --tools seo`).
6. Verdict: KEEP-ON-DEMAND-ONLY (already applied).
7. Layer: L6.

### 2.9 claude-blog

1. Blog suite. 2.3.2. Off at user scope; no project enables it.
2. Cost if on: 32 skills, 2,550 words (source count), 5 agents, 231 words. No hooks.
5. Switch: `enabledPlugins."claude-blog@agricidaniel-blog"` per project (`ai-adopt --tools blog`).
6. Verdict: KEEP-ON-DEMAND-ONLY (already applied). When on, it alone costs more than all OMC skills: keep it strictly per project.
7. Layer: L6.

### 2.10 context7 MCP (inside ai-core)

1. `@upstash/context7-mcp`, launched by `ai-core/mcp/context7.sh` from `~/.local/share/ai/npm/context7-mcp-<version>`. Codex: `mcp_servers.context7`.
2. Cost: 2 deferred tools (names only), 110 words of server instructions.
3. Per call: ai-core PostToolUse matches it (docs-lookup proof).
4. Overlaps: OMC external-context and document-specialist agent, Matt research, OMC research (loser), Microsoft Learn connector, WebSearch. The global rules, the routing row docs-lookup and the server text all say the same thing (3 homes for one rule; plan 6.2 says the server text is enough).
5. Switches: `enabledPlugins` (with ai-core), `permissions.allow mcp__plugin_ai-core_context7__*` (set).
6. Verdict: KEEP-AS-IS. Drop the duplicate text rule and the docs-lookup reminder (plan).
7. Layer: L6.

### 2.11 Playwright MCP (ai-playwright)

1. `ai-playwright-mcp --headless --isolated`. Plugin `ai-playwright@ai` 1.0.0, off at user scope.
2. Cost if on: tool count not measured (not loaded here).
5. Switch: `enabledPlugins."ai-playwright@ai"` per project (`ai-adopt --tools browser`).
6. Verdict: KEEP-ON-DEMAND-ONLY (already applied).
7. Layer: L6.

### 2.12 graphify

1. CLI `graphify` 0.9.112 (`~/.local/bin`), PyPI `graphifyy`. No MCP, no plugin, no Claude hook of its own. Installed by the setup.
2. Cost: only text in the rules (Code navigation section of the global AGENTS.md, 268 words, shared with Serena) and the ai-core nav-first gate.
3. Per call: the nav-first gate denies a broad Grep/rg once per session when a graph exists, and once per graph symbol.
4. Overlaps: Serena, OMC lsp/ast_grep, built-in Explore agent. Use: graphify query 19, update 3, affected 1 in all transcripts.
5. Switches: `.ai/enabled` `no-graph`; `GRAPHIFY_BACKEND=none`, `GRAPHIFY_HOOK_STRICT=0` (set).
6. Verdict: KEEP-AS-IS. The plan wants nav-first measured before a decision.
7. Layer: L6 tool; the nav order = one L5 line.

### 2.13 rtk

1. rtk 1.2.0 (`/opt/homebrew/bin/rtk`). Claude: PreToolUse Bash hook in `~/.claude/settings.json` that runs `rtk-hook` (rtk hook claude; in auto mode a rewrite becomes a deny with "no verdict"). Codex: `rtk hook codex` in `~/.codex/hooks.json`.
2. Cost: the RTK section of the global AGENTS.md, 62 words. 1 hook command per Bash call.
3. Per call: rewrites the command (`git status` becomes `rtk git status`); it filters output (I saw `ls` output cut with "rtk recall" hints during this audit).
4. Overlaps: none in job. Conflict: output filtering can hide lines that an audit or a debug needs (the rules already name `rtk bypass`).
5. Switches: remove the hook entry; `rtk bypass <cmd>`; `RTK_TELEMETRY_DISABLED=1` (set).
6. Verdict: KEEP-AS-IS. Point the hook at the plugin cache path, not the checkout, or keep it on purpose and say so (today a checkout change goes live at once, unlike the router).
7. Layer: L3 (a command rewrite).

### 2.14 herdr

1. Herdr 0.9.5 (`~/.local/bin/herdr`) and the Herdr app (`~/.config/herdr-app`). Hooks in `~/.claude/settings.json`: SessionStart `session-note.sh` (10 s), SessionStart `herdr-agent-state.sh` (10 s), PermissionRequest `ask-hook.sh` (1,800 s). Codex: the same 3. Installed by the setup and the Herdr app.
2. Cost: SessionStart text 437 words (only inside a Herdr terminal, `HC_TERMINAL_ID` set). It asks for emoji reactions and Shepherdr feedback.
3. Per call: PermissionRequest waits up to 30 minutes for an answer from the chat card. It never decides by itself.
4. Conflicts: "react to some of the person's messages with one emoji" against the owner's STE writing style (no rule for emoji, but "Keep them short") and against the Claude Code agent prompt "avoid using emojis". Two PermissionRequest hooks for Bash: herdr ask-hook and OMC permission-handler (auto-allow). The OMC hook can answer "allow" for a command that the owner would see on the card. Use: 286 reaction lines in transcripts, so the owner sees and keeps this.
5. Switches: Herdr Settings "Reactions" and "Feedback for Shepherdr" (the note says "on in Settings"); remove the hook entries; outside Herdr the note prints nothing.
6. Verdict: KEEP-WITH-CONFIG. Ask the owner if Reactions are wanted; if not, switch off in Herdr Settings (estimate: removes about 280 of the 437 words).
7. Layer: L6 tool; the session note = L5 (only inside Herdr); the ask hook = L3 transport for permissions.

### 2.15 Matt Pocock skills

1. 27 skills in `~/.local/share/ai/plugins/mattpocock-skills` (git `mattpocock/skills`, newest stable). Linked per project by ai-adopt (15 in <project-a>) and 6 at user scope.
2. Cost: model-invocable ones show in the listing: project 8 entries, 263 words (code-review 70, codebase-design 42, diagnosing-bugs 21, domain-modeling 25, pr 8, prototype 34, research 41, tdd 22); user grilling 27, writing-for-agents 17. Typed-only (disable-model-invocation): ask-matt, grill-me, grill-with-docs, handoff, implement, implement-spec, improve-codebase-architecture, retro, setup-matt-pocock-skills, teach, to-questionnaire, to-spec, to-tickets, triage, wait-what, wayfinder: 0 words in the listing, but the ai-core skill card lists their folders.
3. Per call: none.
4. Overlaps: OMC (plan, tdd, review, research, pr, deep-interview, teach, debug); ponytail-review; bundled security-review and simplify. The winner gate already makes Matt the winner for 8 jobs.
5. Switches: per-project links (`.ai/enabled` `skills:` line); `skillOverrides` works for these (not plugin skills).
6. Verdict: KEEP-AS-IS. Use (all transcripts): writing-for-agents 68, diagnosing-bugs 25, tdd 12, code-review 7, research 6, grilling 6, pr 4, codebase-design 3, domain-modeling 2; typed /to-tickets 2, /improve-codebase-architecture 2, /ask-matt 2.
7. Layer: L6, with one L5 index line each.

### 2.16 pstack verification skills

1. create-verification-skill and maintain-verification-skill from `cursor/plugins` folder `pstack` (default-branch HEAD), copy in `~/.local/share/ai/plugins/pstack-verification`, linked in `~/.claude/skills` and `~/.agents/skills`.
2. Cost: 2 entries, 119 words (70 + 49).
4. Overlaps: OMC `create-verification-skill` and `maintain-verification-skill` (same bare names, both listed); OMC verify skill and verifier agent; ai-core stop-check; ship. The routing.yaml row "Prove a feature works" has `losers: []`, so nothing stops the OMC copies.
5. Switches: the links; `skillOverrides` (works for these, not for the OMC copies).
6. Verdict: REPLACE-OVERLAP. pstack wins. Silence the OMC copies with the winner gate: add `oh-my-claudecode:create-verification-skill` and `oh-my-claudecode:maintain-verification-skill` to `losers` of "Prove a feature works" in `ai/routing.yaml`.
7. Layer: L6; the proof check = L4.

### 2.17 anthropic-skills pack (claude.ai synced)

1. 11 org skills synced from claude.ai into `~/.claude/skills/synced/` (bi-guided-analytics, <org>, docs, docx, google-workspace, import-memory, morning, pdf, pptx, skill-creator, xlsx).
2. Cost: 11 names, 22 words (name-only in the listing).
4. Overlaps: anthropic-skills:docs and the Claude Docs connector; import-memory against the owner's "no auto memory" rule (only if used).
5. Switches: `skillOverrides` (works for synced skills: `Mv()` strips the `anthropic-skills:` prefix); `CLAUDE_CODE_SYNC_SKILLS`.
6. Verdict: KEEP-AS-IS (22 words).
7. Layer: L6.

### 2.18 claude.ai connectors

1. 38 claude.ai MCP connectors attach to each Claude Code session from the account (Microsoft 365 50 tools, Claude Data 11, Google Calendar 9, Claude Docs 8, Google Drive 8, Google Sheets 6, Meetings 5, Google Slides 4, Microsoft Learn 3, and 29 servers that only show `authenticate` / `complete_authentication`).
2. Cost: server instructions 1,071 words (Claude Data 177, Claude Docs 296, Google Docs 17, Google Sheets 17, Google Slides 8, Meetings 341, Microsoft Learn 215); about 208 deferred tool names (about 9,800 characters, about 2,450 tokens). Claude Docs `batch`, `guide`, `update` came up front in this subagent.
3. Per call: none.
4. Overlaps: Microsoft Learn and context7 (docs); Claude Docs and the Artifact tool and anthropic-skills:docs; the Claude Docs instructions say "Make a doc here ... FIRST ... a reflex", which competes with the owner's rule "Knowledge lives in the repo only". Use in all Claude Code transcripts: 1 Google Drive call; Claude Docs 0 calls.
5. Switches: `"disableClaudeAiConnectors": true` in any settings file (user or project); env `ENABLE_CLAUDEAI_MCP_SERVERS=false`; `deniedMcpServers` for single servers.
6. Verdict: KEEP-WITH-CONFIG. Set `disableClaudeAiConnectors: true` in `~/.claude/settings.json` (Claude Code only; claude.ai keeps them). If the owner wants one connector in code sessions, use `deniedMcpServers` for the rest instead.
7. Layer: L6 (on demand, by project).

### 2.19 Bundled Claude Code skills

1. 16 skills from Claude Code itself.
2. Cost: 1,024 words (dataviz 219, claude-api 143, artifact-capabilities 120, update-config 98, schedule 65, run 63, loop 61, plugin-authoring 52, workflow-authoring 38, artifact-diagramming 33, keybindings-help 32, simplify 30, artifact-design 29, fewer-permission-prompts 25, security-review 14, init 2).
4. Overlaps: simplify and security-review with OMC and Matt review; run with verify-<app>.
5. Switches: `skillOverrides` per name with `on | name-only | user-invocable-only | off` (works for bundled skills); `disableBundledSkills`; `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS`; `skillListingMaxDescChars` (default 1536); `skillListingBudgetFraction` (default 0.01 of the context).
6. Verdict: KEEP-WITH-CONFIG. In `~/.claude/settings.json` `skillOverrides`: `"dataviz": "name-only"`, `"claude-api": "name-only"`, `"artifact-capabilities": "name-only"`, `"update-config": "name-only"`, `"schedule": "name-only"`, `"run": "name-only"`, `"loop": "name-only"`, `"plugin-authoring": "name-only"`, `"workflow-authoring": "name-only"`, `"keybindings-help": "name-only"`. Estimate: removes about 800 words. The skills stay callable.
7. Layer: L6.

### 2.20 Owner's own items

- `999-ads` (68 words, 13 uses), `omc-reference` (30 words; CLAUDE.md names it): KEEP-AS-IS, L6.
- `~/.claude/agents/json-aberration-analyzer.md`: 190 words in each session's agent listing; 0 uses in all 203 transcript folders. DROP-CANDIDATE: the proof covers this Mac only; it is a personal file, so the owner moves it.
- `~/.claude/hooks/caveman-*.js`: not wired, 0 cost; `AI_DROP_CLAUDE_HOOKS` already lists them. DROP-CANDIDATE (owner's personal folder).
- `typesafe@typesafe-ai`: off, 0 cost, 0 uses. KEEP-ON-DEMAND-ONLY (keep off; removal saves nothing).

## A. Table of all extensions (Claude, one new session in <project-a>)

| Extension | Always-loaded words | Skills (listing words) | Agents (words) | MCP tools | Hook commands | Verdict |
|---|---|---|---|---|---|---|
| ai-core | 137 start text | 1 (54) | 0 | context7: 2 deferred, 110 words instr. | 12 (+ rtk 1 in settings) | KEEP-WITH-CONFIG |
| ai-serena / Serena | 21 instr. | 0 | 0 | 14 up front, about 2,100 words | 0 (1 SessionEnd in ai-core) | KEEP-WITH-CONFIG |
| ponytail | 493 (+493 per subagent) | 6 (253) | 0 | 0 | 3 + band module | KEEP-WITH-CONFIG |
| i-have-adhd | 1,215 | 1 typed-only (0) | 0 | 0 | 1 | REPLACE-OVERLAP |
| oh-my-claudecode | 15 (memory, grows) | 76 (1,558) | 19 (305) | t: 50 deferred | 31 + jev module | KEEP-WITH-CONFIG |
| oh-my-codex (Codex) | 3,380 AGENTS.md + 144 dev instr. | 24 | 33 prompts | 0 | 8 (+notify) | KEEP-WITH-CONFIG |
| ui-ux-pro-max | 0 | 7 (339) | 0 | 0 | 0 | KEEP-ON-DEMAND-ONLY (applied) |
| claude-seo | 0 (off) | 29 (1,252 if on) | 20 (497 if on) | 0 | 1 if on | KEEP-ON-DEMAND-ONLY (applied) |
| claude-blog | 0 (off) | 32 (2,550 if on) | 5 (231 if on) | 0 | 0 | KEEP-ON-DEMAND-ONLY (applied) |
| context7 MCP | 110 instr. | 0 | 0 | 2 deferred | 0 | KEEP-AS-IS |
| Playwright MCP | 0 (off) | 0 | 0 | not loaded | 0 | KEEP-ON-DEMAND-ONLY (applied) |
| graphify | 0 (rules text only) | 0 | 0 | 0 | 0 (ai-core gate) | KEEP-AS-IS |
| rtk | 62 rules text | 0 | 0 | 0 | 1 | KEEP-AS-IS |
| herdr | 437 (in Herdr only) | 0 | 0 | 0 | 3 | KEEP-WITH-CONFIG |
| Matt Pocock skills | 0 | 10 model-invocable (307) | 0 | 0 | 0 | KEEP-AS-IS |
| pstack verification | 0 | 2 (119) | 0 | 0 | 0 | REPLACE-OVERLAP (pstack wins) |
| anthropic-skills (synced) | 0 | 11 (22) | 0 | 0 | 0 | KEEP-AS-IS |
| claude.ai connectors | 1,071 instr. | 0 | 0 | about 208 deferred | 0 | KEEP-WITH-CONFIG |
| Bundled Claude Code skills | 0 | 16 (1,024) | 6 built-in (366) | 0 | 0 | KEEP-WITH-CONFIG |
| Setup user skills (ship, release, ...) | 0 | 6 (420) | 0 | 0 | 0 | KEEP-AS-IS |
| Owner items (999-ads, omc-reference, json agent) | 0 | 2 (98) | 1 (190) | 0 | 0 | KEEP / DROP-CANDIDATE (json agent) |
| typesafe | 0 (off) | 1 (96 if on) | 0 | 0 | 0 | KEEP-ON-DEMAND-ONLY |

Hook commands registered for Claude today: ai-core 12, user settings 4 (herdr 3, rtk 1), OMC 31, ponytail 3, i-have-adhd 1. Total 51 commands and 2 hook modules.

Hook processes per Bash call today: PreToolUse 4 (ai-core router, rtk, OMC pre-tool-enforcer, OMC git-guardrails) and PostToolUse 3 (router, OMC verifier, OMC project-memory). Per Read: PreToolUse 2, PostToolUse 5. Per Stop: 7. Per new session: 12 at startup.

## B. Fixed cost of one new Claude session (<project-a>, this Mac, today)

| Source | Words today | Tokens today (x1.4) | After verdicts (words) | After (tokens) | What changes |
|---|---|---|---|---|---|
| Rules files: `~/.config/ai/AGENTS.md` 3,133; `~/.claude/CLAUDE.md` 38; project `AGENTS.md` 269, `CLAUDE.md` 1, `CLAUDE.local.md` 238 | 3,679 | 5,151 | 1,296 (global 600 target, plus 150 output style) | 1,814 | plan Phase 3 + output style |
| Session-start hook text: i-have-adhd 1,215, ponytail 493, herdr 437, ai-core 137, OMC 15 | 2,297 | 3,216 | 718 (ponytail 493, herdr about 150, ai-core 60, OMC 15) | 1,005 | adhd flag, herdr settings, ai-core status line |
| Skill descriptions (137 entries): OMC 1,558, bundled 1,024, user 681, ui-ux 339, Matt project 263, ponytail 253, ai-core 54, synced 22 | 4,194 | 5,872 | about 3,390 | 4,746 | bundled name-only |
| Agent descriptions (26): built-in 366, OMC 305, json-aberration-analyzer 190 | 861 | 1,205 | 671 | 939 | json agent moved out |
| MCP server instructions: claude.ai 1,071, context7 110, serena 21 | 1,202 | 1,683 | 131 | 183 | connectors off |
| MCP tool schemas up front: Serena 14 tools (estimate) | about 2,100 | 2,940 | about 900 | 1,260 | Serena excluded_tools |
| Deferred tool names: 228 names, 10,889 characters | n/a | about 2,720 (chars/4) | about 70 names | about 830 | connectors off |
| Total | about 14,330 words + names | about 22,790 tokens | about 7,110 words + names | about 10,780 tokens | -53 percent |

Notes:
- The rules-file row uses the per-file counts of the transcript `instructions` attachment (3,133 + 38 + 269 + 1 + 238).
- Not in the table: Claude Code's own system prompt (752 words in the prompt snapshot) and its built-in tool schemas. They are not extensions.
- herdr text loads only in a Herdr terminal. CLAUDE.local.md loads only in <project-a>.
- The OMC skill listing (1,558 words) and agents (305 words) stay in the "after" column, because no switch removes them while the plugin is on. With OMC per project only (the D6 option), subtract a further 1,863 words (2,608 tokens) in projects without OMC.
- Per-subagent cost today: ponytail 493 words in each subagent. Per long session: OMC per-call text measured at about 4,000 words in session 690a8739 (1,200 + 394 + 360 + 250 + 240 + 160 + 120 + 110 + 108 + 60 + 9 + the 1,791-word persisted outputs not counted).
- Codex session (not in the table): `~/.codex/AGENTS.md` 6,629 words + `developer_instructions` 144 words + ai-core, ponytail and i-have-adhd start text.

## C. Overlap matrix

| Job | Sources that offer it | Winner | Mechanism that silences the others (no uninstall) |
|---|---|---|---|
| Planning | Matt to-spec, to-tickets, wayfinder; OMC plan, omc-plan, ralplan, planner agent, analyst agent; OMX plan, ralplan; built-in Plan agent | Matt to-spec / to-tickets (wayfinder for big unclear work) | Winner gate (already lists OMC and OMX plan, ralplan). Agents: `permissions.deny` `Agent(oh-my-claudecode:planner)` (syntax for 2.1.325 not verified) or leave as optional helpers |
| Spec and tickets | Matt to-spec, to-tickets, to-questionnaire, triage; OMC sdd, stacked-delivery; routing row tracker-flow | Matt | Add `oh-my-claudecode:sdd` to winner-gate losers; delete the tracker-flow reminder (plan D1) |
| TDD | Matt tdd; OMC tdd, test-engineer agent; ai-core tdd nudge | Matt tdd | Winner gate (OMC tdd is a loser, works). Remove the dead `skillOverrides` entry. Drop the nudge (plan D1) |
| Debugging | Matt diagnosing-bugs; OMC debug, trace, tracer agent, debugger agent; ai-core diagnosing-bugs nudge | Matt diagnosing-bugs; OMC tracer/debugger as subagents | Skill description carries the trigger; drop the nudge; OMC debug is about OMC state, keep |
| Code review | Matt code-review; OMC review, omc-review, interrogate, code-reviewer agent (74 uses); ponytail-review, ponytail-audit; bundled simplify; OMX code-review | Matt code-review (it may use the OMC code-reviewer agent as worker) | Winner gate already has OMC review; add `ponytail:ponytail-review` and `oh-my-claudecode:interrogate` to losers if the owner wants one voice |
| Security review | Bundled security-review; OMC security-reviewer agent (16 uses); ship step; OMC interrogate | ship (it runs the bundled security-review) | No silencing needed: one is a skill, one is a worker |
| Verification | pstack create/maintain-verification-skill; OMC create/maintain-verification-skill, verify, verifier agent; ai-core stop-check; ship; OMC workflow-drift-guard | pstack + stop-check (L4) + ship | Winner gate losers for the 2 OMC copies (skillOverrides is a no-op); `OMC_SKIP_HOOKS` token `workflow-drift-guard` if its blocks are not wanted |
| Memory and knowledge | Repo Map, GLOSSARY.md, docs/adr; OMC project-memory (auto), wiki, remember, notepad; Serena memories (not exposed now); Claude auto memory (off: `autoMemoryEnabled: false`); claude.ai Claude Docs; anthropic-skills:import-memory | Repo docs | Winner gate (OMC wiki loser); `OMC_SKIP_HOOKS` `project-memory-posttool` stops writes; the start injection has no switch except OMC off; connectors off |
| Navigation | graphify; Serena; OMC lsp_* and ast_grep_*, explore agent; built-in Explore agent; rtk grep | graphify, then Serena | `OMC_SKIP_HOOKS` `post-tool-use` (removes "Consider using Grep"); Serena `excluded_tools` `initial_instructions` (removes "CRITICAL"); OMC lsp tools stay deferred |
| Docs lookup | context7; Matt research; OMC research, external-context, document-specialist agent; Microsoft Learn connector; WebSearch | context7 | Winner gate (OMC research loser); connectors off; drop the text copy in AGENTS.md |
| Reply style | Global AGENTS.md (244 words of style text), i-have-adhd (1,215), ponytail (493 incl. closing line), OMC minimal-prose-discipline and bro (on demand), herdr reactions, Claude Code system prompt | One output style (section D) | Delete `~/.claude/.i-have-adhd-always`; style file owns the closing line; Herdr Reactions off if not wanted |
| Git and PR flow | Setup gates + global rules + Matt pr + ship + release; OMC pr, git-master agent, babysit, fix-ci, get-pr-comments, fix-merge-conflicts, stacked-delivery, release (loser), git-guardrails; OMX | Setup gates + Matt pr + ship | Winner gate (OMC pr, release losers); `OMC_GIT_GUARDRAILS=0` only if it gets in the way (it is off outside unattended modes) |
| UI design | ui-ux-pro-max (per project); OMC designer agent, loft, visual-verdict; Matt prototype; bundled artifact-design | ui-ux-pro-max | Already per project; no silencing needed |
| SEO and blog | claude-seo, claude-blog (off); tie-break rules | per tie-break | Already off; `enabledPlugins` per project |
| Notifications | herdr (chat cards, phone); ai-core claude-notify; OMC configure-notifications (`OMC_NOTIFY`); Codex `notify` = OMX notify-hook | herdr | Do not configure OMC notifications; Codex `notify` key can point at herdr instead of OMX (not checked) |
| Permissions and safety | Claude permissions and `autoMode`; ai-core gates (incl. ask-first); OMC permission-handler (auto-allow), git-guardrails, read budget; herdr ask-hook; rtk auto-mode deny; Codex OMX "AUTONOMY DIRECTIVE" | Claude permissions + ai-core gates (L3), herdr as the answer channel | OMC permission-handler: no token switch (only `DISABLE_OMC=1` or plugin off); OMX directive: strip in ai-sync render of `~/.codex/AGENTS.md` |

## D. Reply-style collision

### Sources

| Source | Words | Key demands |
|---|---|---|
| `~/.config/ai/AGENTS.md` (first line, Reporting style, Writing style, Output shape, Characters) | about 244 | "Lead with the answer. Hard limit: 60 words unless I ask for detail. Tables and lists count." STE: 25 words per sentence max, full sentences with articles. "Follow i-have-adhd in every reply." "The 60-word limit has two exceptions: the state line and the one next action." No em dash. PR links in full. |
| i-have-adhd (SessionStart, always-on) | 1,215 | "The first line is something the reader can do. Not context. Not a plan. The action." Number multi-step tasks. "End with one concrete next action." "Restate state every turn." "Give specific time estimates." "Cap lists to 5 items." "No preamble, no recap, no closing pleasantries." Pre-send: delete "the last sentence if it ... recaps what just happened". |
| ponytail (SessionStart and each SubagentStart) | 493 (of which about 40 words on the reply) | "End your reply with one or two lines: what you skipped or did not check, and any risk the user must know." Plus "a reply a busy human understands in one read" (skill description). |
| OMC | 0 always; on demand: minimal-prose-discipline, bro, technical-writing | "filler dies, no narration"; "auto-clarity where terse misleads". The "Use parallel execution ..." texts are not style, but they add noise. |
| herdr session note | 437 (Herdr only) | Emoji reactions on some messages; `<hc no-reply/>` for a message that needs no words. |
| Output style | none set (`outputStyle` absent) | - |
| Claude Code system prompt | part of 752 | Report outcomes plainly; recommend, do not survey. |

### Contradictions

1. First line: the global rules say "Lead with the answer"; i-have-adhd says the first line is "the action", "Not context". For a question ("why is X slow?") these give different first lines.
2. Last line: i-have-adhd says "End with one concrete next action" and "delete ... the last sentence if it ... recaps what just happened"; ponytail says "End your reply with one or two lines: what you skipped or did not check". Both claim the last line. A "not checked" line can look like a recap to the i-have-adhd pre-send check.
3. Length: the 60-word cap against i-have-adhd's "restate state every turn", "time estimates", and ponytail's closing line. The owner already exempts the state line and the next action, but not ponytail's line.
4. Subagents: ponytail's closing-line rule reaches each subagent; i-have-adhd does not. A subagent report then follows a different shape than the main reply (this audit's own brief asks for "a summary under 500 words", which ponytail and the 60-word rule do not cover).
5. Herdr: emoji reactions against the Claude Code instruction "avoid using emojis" (subagent prompt) and the tone of STE.
6. Codex: the same two plugins inject there too, but Codex has no output style; the OMX block adds its own working agreements.

### Proposal: one source

Create one Claude output style, for example `~/.claude/output-styles/owner.md`, and set `"outputStyle": "owner"` in `~/.claude/settings.json`. Mirror the same text as the first block of the rendered `~/.codex/AGENTS.md`. Draft (about 150 words):

1. The first line is the answer. If the task asks for work, the first line says what was done.
2. Hard limit: 60 words, lists and tables count. Code blocks, the state line and the last two lines do not count. More only when the owner asks for detail or says "explain".
3. Use numbered steps for 2 or more steps. 5 items max per list.
4. Write in ASD-STE100 style: full sentences, 25 words max each, exact numbers, units, versions and paths.
5. State line, when the work has steps: "Step N of M: <what>."
6. The last two lines, in this order: "Not checked: <what was skipped or not verified, and any risk>." Then "Next: <one action the owner can do in 2 minutes>."
7. No preamble, no recap, no pleasantries, no em dash.

Then: delete `~/.claude/.i-have-adhd-always` (i-have-adhd stays as `/i-have-adhd`); keep ponytail `full` for its coding rules (its closing line is now the style's line 6, so the two agree); remove the reply-shape copies from `~/.config/ai/AGENTS.md` and leave one line "Reply shape: the owner output style". The plan's D4 test (obedience before and after) still applies.

## E. The 10 highest-value configuration changes

Ranked by tokens saved or conflicts removed per unit of risk.

| Rank | Change | Exact file and key | Effect | Risk |
|---|---|---|---|---|
| 1 | Stop the always-on i-have-adhd print; add the output style | Delete `~/.claude/.i-have-adhd-always`; create `~/.claude/output-styles/owner.md`; `~/.claude/settings.json` `"outputStyle": "owner"` | -1,215 words (about 1,700 tokens) per session; removes 3 reply contradictions | Low; `/i-have-adhd` still works |
| 2 | claude.ai connectors off in Claude Code | `~/.claude/settings.json` `"disableClaudeAiConnectors": true` (or env `ENABLE_CLAUDEAI_MCP_SERVERS=false`) | -1,071 words of instructions and about 208 deferred names: about 4,000 tokens; removes the Claude Docs "make a doc FIRST" voice | Low: 1 connector call in all transcripts |
| 3 | Stop OMC shell-history writes | `~/.claude/.omc-config.json` `"bashHistory": false` | No more agent commands in `~/.bash_history` (20 MB now); a personal-file and secret-leak risk goes away | None |
| 4 | Silence OMC per-call text | `~/.claude/settings.json` `env.OMC_SKIP_HOOKS = "keyword-detector,skill-injector,pre-tool-use,post-tool-use,post-tool-use-failure,project-memory-posttool"` and `env.OMC_QUIET = "2"` (same in `~/.codex/config.toml` `shell_environment_policy.set`) | Removes about 4,000 words per long session, the AGENTS.md re-injection (up to 5,000 tokens per file), the 70 percent nag, the read-budget deny | Low to medium: OMC TODO status lines and read budget go too |
| 5 | Ship the narrowed ai-core manifest | `~/.dotfiles-ai/ai/marketplace/plugins/ai-core/.claude-plugin/plugin.json` `version` bump (for example 1.0.1), then reinstall | PreToolUse router stops on Read, Glob, Agent, Task; `onFailure: block` holds the gates; the cache matches origin | Low |
| 6 | Trim Serena tools | `~/.serena/serena_config.yml` `excluded_tools: [execute_shell_command, serena_repl, find_declaration, find_implementations, get_diagnostics_for_file, insert_after_symbol, replace_content, replace_in_files, safe_delete_symbol, initial_instructions]` | About -1,200 words (estimate) per session; removes the "CRITICAL: call initial_instructions" voice | Low: 0 calls to these tools in all transcripts |
| 7 | Bundled skills to name-only | `~/.claude/settings.json` `skillOverrides`: `dataviz`, `claude-api`, `artifact-capabilities`, `update-config`, `schedule`, `run`, `loop`, `plugin-authoring`, `workflow-authoring`, `keybindings-help` = `"name-only"` | About -800 words per session | Low: the skills stay callable |
| 8 | Replace the dead skillOverrides with winner-gate losers | `~/.dotfiles-ai/ai/routing.yaml` `winners.table` row "Prove a feature works" `losers: ['oh-my-claudecode:create-verification-skill', 'oh-my-claudecode:maintain-verification-skill']`; remove the 3 OMC entries from `~/.claude/settings.json` `skillOverrides` and the 3 from `<project-a>/.claude/settings.json` (and from the ai-adopt template) | Removes the false belief that 6 skills are off; one working silencer | Low |
| 9 | Shrink the global rules file | `~/.dotfiles-ai/ai/agents-md/*` (rendered to `~/.config/ai/AGENTS.md`), plan Phase 3, cap via `AGENTS_CAP` | 3,133 to about 600 words: about -3,500 tokens per session | Medium: needs the E1 verdict list and the D3 owner pass |
| 10 | Remove the OMX autonomy directive in Codex | ai-sync render of `~/.codex/AGENTS.md`: drop the block between `<!-- AUTONOMY DIRECTIVE` and `<!-- END AUTONOMY DIRECTIVE -->` (an OMX setting for it: not checked) | Removes a direct contradiction with the `ask-first` gate and the deploy rule | Medium: OMX setup can write the block back; check after each OMX update |

Next in line: Herdr Settings "Reactions" off (about -280 words, owner choice); move `~/.claude/agents/json-aberration-analyzer.md` out (-190 words, owner's file); ponytail plugin option `ledger` false (no per-turn CSV writes).

## F. Edge cases for the redesign

1. If a plugin's hooks are off:
   - ai-core hooks off (`disableAllHooks`, plugin off, or a hook crash without `onFailure: block` in the installed cache): every L3 gate and the L4 stop-check are gone; nothing else in the setup enforces them (L1 and L2 must carry them, plan Phase 2).
   - OMC hooks off (`DISABLE_OMC=1`): persistent modes (ralph, autopilot, ultragoal, team) lose their Stop continuation and state tracking; `cancel` and HUD still work; the agents and skills still load. The context guard at 94 percent goes too.
   - ponytail `off`: no ruleset in the main session or subagents; skills stay.
   - herdr hooks off: no chat card for permissions; the terminal prompt still works.
   - rtk hook off: no rewrite; output is longer; nothing breaks.
2. Self-re-enabling or settings rewrites:
   - install.sh re-writes `enabledPlugins` false for `AI_OFF_CLAUDE_PLUGINS` on each run, and `claude plugin update` re-installs plugins. An owner change by hand in `enabledPlugins` for those 4 plugins does not survive a run.
   - ai-core keeps version 1.0.0, so Claude Code does not refresh the cache by itself; the setup must reinstall. The rtk hook points into the checkout, so it changes at once on a branch switch.
   - OMC `omc-setup` writes the statusLine and a `CLAUDE.md` block (install.sh replaces the long block with a 3-line note); OMC session-start replaces older cache version folders with symlinks to the newest; OMC update checks are blocked by `OMC_UPDATE_REGISTRY_BASE=http://127.0.0.1:9`.
   - ponytail `/ponytail default <level>` writes `~/.config/ponytail/config.json`; i-have-adhd reads its flag file at each start.
   - OMX setup can rewrite `~/.codex/AGENTS.md` OMX blocks (markers in the file); `OMX_AUTO_UPDATE=0` is set.
   - `DISABLE_AUTOUPDATER=1` stops Claude Code self-updates.
3. Hooks from other plugins that can still block a turn or a tool call:
   - PreToolUse deny: OMC pre-tool-enforcer (read budget, forced delegation), OMC git-guardrails (in unattended modes or `OMC_GIT_GUARDRAILS=1`), rtk-hook (deny in auto mode when it would rewrite).
   - PermissionRequest: OMC permission-handler can ALLOW a "safe" Bash command; herdr ask-hook can hold a request up to 1,800 s.
   - Stop block: OMC context-guard (94 to 95 percent, 2 times), workflow-drift-guard (option question, TODO claim), persistent-mode (active mode), budget-guard (only with `OMC_BUDGET_ENFORCE=active`), code-simplifier (only if enabled). With ai-core stop-check, one Stop can get 2 different block reasons in a row.
   - SubagentStop: OMC verify-deliverables (5 s).
   - UserPromptSubmit: ponytail tracker, OMC skill-injector can add text; none blocks today.
4. What a project `.claude/settings.json` can override (Claude Code 2.1.325, from the settings schema text): precedence user < project < local < flag < policy.
   - `enabledPlugins`: a project can turn ai-core, OMC or any plugin off or on ("setting false in ~/.claude/settings.json is overridden by the project"). This contradicts the plan's line "A project cannot loosen the core" (6.7) unless Phase 8 pins ai-core in managed settings.
   - `disableAllHooks: true` in a project turns off all hooks, the plugin hooks and the statusLine.
   - `env`: a project can set `OMC_SKIP_HOOKS`, `DISABLE_OMC`, `PONYTAIL_DEFAULT_MODE`, `OMC_GIT_GUARDRAILS` and so on.
   - `permissions.allow` adds; `deny` rules add up and win.
   - `skillOverrides`: works for project, user, bundled and synced skills; not for third-party plugin skills.
   - `disableClaudeAiConnectors`: "any-source-true wins: a project can opt out, but a project-level false cannot override a user-level true."
   - `outputStyle`, `hooks` (adds hooks), `statusLine`.
   - Only managed settings can stop this (`allowManagedHooksOnly`, managed `enabledPlugins`, `prependPlugins` to run the core hooks first).
5. Other edge cases:
   - The skill listing has a budget (`skillListingBudgetFraction` default 0.01 of the context). When it overflows, later entries lose their descriptions (many OMC entries are name-only now). A new plugin can push the setup's own skills to name-only, depending on order.
   - Codex trusts hooks per script hash; a router change needs a new trust in Codex (ai-core README).
   - OMC `.omc/` and `.claude/skills/.omc/` appear in each project; the omc routing rule says keep `.omc/` out of commits.

## G. Not checked

- The exact token count of the Serena tool schemas (estimated from the schemas in my own context, about 2,100 words).
- Whether Serena tools are up front because of a server flag (`anthropic/alwaysLoad`) or another rule; how to make them deferred.
- OMX: per-call text of `codex-native-hook.js`, its switches, and whether an OMX setting removes the AUTONOMY DIRECTIVE.
- The Codex session fixed cost in tokens (no Codex transcript was read).
- The exact settings key where Claude Code stores ponytail `userConfig` values (`ledger`).
- The `permissions.deny` syntax for a named subagent (`Agent(<name>)`) in 2.1.325.
- Herdr: the size of the note with Reactions and Feedback off (the 150-word figure is an estimate).
- ai-playwright tool count and text (not loaded here).
- claude-seo, claude-blog and typesafe text was counted from the source, not from a live session.
- Typed slash-command use was counted only from `<command-name>` records; usage counts cover this Mac only (not <server>, not <second-mac>).
- The 6.4 plan target of 600 words is taken as the "after" number; I did not draft that text.
- I did not run any hook, did not run `ai-doctor`, and did not test any switch live.
