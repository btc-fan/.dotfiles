# AI setup spec (branch `ai`)

Clean, current version. Decision history and reasons: `ai/SPEC-LOG.md`. Where they differ, this file wins.
Status: owner decisions of 2026-11-11 recorded (section 17); final approval pending. Scope: build everything at once.
Order (owner 2026-11-11): minimal `ubuntu-server` branch first, then the `ai` build and its server test.

## 0. Purpose and principles
- One AI setup for every machine (macOS, Ubuntu; Windows later) and every future project.
- Every tool is audited before use, pinned to the audited version, and wired globally so no project can forget it.
- Every MCP and skill has a usage contract (section 8): we know how to use it, it is used every time it
  applies, and we can prove it fired.
- Telemetry off and auto-updates off in every tool. Updates happen only after a new audit.
- The repo is PUBLIC: no secrets, no host names, no personal data (one owner-approved exception: section 13).
- Keep it simple where it does not cost reliability.

## 1. Repo, branches, install model
- Repo `btc-fan/.dotfiles`. Branches: `main` (macOS base), `windows`, `ai` (this), `ubuntu-server` (TODO, section 14).
- Layout on every machine (owner 2026-11-10): one repo, two folders.
  - `~/.dotfiles` = the OS base branch (`main` macOS, `windows`, `ubuntu-server`), set up first by its README.
  - `~/.dotfiles-ai` = branch `ai` via `git worktree add ~/.dotfiles-ai ai` (checking out `ai` in ~/.dotfiles
    would break the base branch's stowed links).
  - AI install links `~/.dotfiles/bin/claude-notify` (and other bin entries) to `~/.dotfiles-ai/ai/bin/`
    (ignored in the base worktree via .git/info/exclude), so the owner's hooks.json (A.2) works unchanged.
  - Every base branch README ends with an "AI setup" section: the 2 to 3 commands that add `~/.dotfiles-ai`
    and run its install.sh. Applies to `main`, `windows` and `ubuntu-server`.
- Work tree for building: `~/work/dotfiles-ai` (git worktree). `~/.dotfiles` on the Mac is never edited
  (it holds an uncommitted `.zshrc` with live secrets: never commit, move or edit it).
- `ai` has no upstream to `main`. Push only after owner approval and a secret scan.
- Distribution:
  - GNU stow for plain files.
  - rulesync (pinned, audited, piloted in a throwaway HOME on the home server first; owner 2026-11-11:
    "rulesync after a pilot") writes rules, MCP, skills and hooks into each agent's own format.
    If the pilot fails, small own adapters do the same job (owner is told before switching).
  - Own small adapters only for gaps: herdr, omo, oh-my-claudecode, oh-my-codex, Hermes SOUL.md.
  - Files that tools also write (`~/.claude/settings.json`, `~/.claude.json`, `~/.codex/config.toml`,
    `~/.hermes/config.yaml`): merge our keys only, never own the whole file.
- `install.sh`: one entry for macOS + Ubuntu. Asks "Is this a new Ubuntu server ...?" (default NO); the server
  scripts themselves live in `ubuntu-server`.
- Always-on Claude plugins: private marketplace in this repo, one bundle plugin `ai-core` with pinned
  `dependencies` (commit sha where a tool has no tags). Codex: plugins one by one + AGENTS.md text.
- Delivery: build -> secret scan -> push `ai` -> test install on the home server from `~/.dotfiles-ai` ->
  show owner the whole setup -> install on the Mac. Then `ubuntu-server` branch; then "AI setup" sections
  in the `main` and `windows` READMEs.
- Goal: pull the repo, run the README commands, get the whole setup on any machine.
- Repo contents: README.md, docs/INSTALL.md, docs/CONTEXT.md (lists of rules, agents, MCP, plugins, skills,
  hooks, routing, toolbox), docs/EXTENDING.md, install.sh, secrets.env.example, ai/ (AGENTS.md, routing.yaml,
  rules/, adapters/, hooks/, bin/, marketplace/, skills/, mcp/, evals/, TOOLBOX.md, SPEC.md, SPEC-LOG.md).
- README (owner: "super clear on how all this works, absolutely"): what it is; how every part works (agents,
  tools, routing layers, hooks, usage contracts) with one diagram; exact install commands per OS; per-machine
  one-time steps (logins, `/seo setup`, secrets.env); how to verify (`ai-doctor`); how to update; how to remove;
  where things live on disk; troubleshooting.
- docs/EXTENDING.md (owner: "we will work a lot there"): step-by-step to add a skill, MCP server, plugin,
  routing rule or toolbox entry: intake + audit -> usage contract (ai/rules/<tool>.md) -> routing.yaml row
  -> evals -> re-run install -> ai-doctor; how to bump a pinned version (re-audit); how to retire a tool.

## 2. Root rules: ai/AGENTS.md
Composed from, in this order:
1. Owner text VERBATIM (Appendix A.1).
2. Sections in the same short plain style:
   - Output shape: follow i-have-adhd, always on; its "when to break the rules" list applies; off for a
     session only when the owner says "stop adhd mode"; state + one next action may go past 60 words.
   - RTK: owner block A.4 is the source text.
   - Code navigation: graphify first, then Serena, then read only located lines (section 4 / contracts).
   - Audit before use: run `agent-audit` before any package, MCP server, skill or plugin; findings = stop and
     show the owner; no tool that uploads code, prompts or telemetry.
   - Pull requests: summary, Mermaid diagram of the change, "one-way or two-way door?", blast radius.
   - PR author-sessions note: owner block A.5 verbatim.
   - Characters: never the em dash (U+2014); use "-", ":" or a new sentence.
   - Prompting other agents (about 10 lines): goal + what is ruled out, name files, narrow scope, expected
     output and format, read-only unless the owner says otherwise.
   - Tool catalog: per harness: strength, non-interactive command, JSON output flag, power and limits, docs link.
   - L0 routing table (rendered from routing.yaml, section 7).
   - Toolbox pointer: "For specialized work, check ~/.config/ai/TOOLBOX.md for a ready tool before building one."
   - Vendor rules of every global tool, imported from ai/rules/<tool>.md (section 8).
- No git/jj section. No "simple language" section (STE covers it).
- Global rules are a must. A project AGENTS.md adds rules and may override only style or tooling details.
- Each agent gets a thin file that imports or links the root plus agent-only lines.
- Each project: its own AGENTS.md + a 1-line CLAUDE.md `@AGENTS.md` (Claude skips AGENTS.md if any CLAUDE.md exists).
- Opt-in tools' vendor rules go inside managed blocks in the project AGENTS.md, one per tool with name and
  version in the markers (`<!-- AI:<tool> v<N> START --> ... <!-- AI:<tool> v<N> END -->`), upserted by marker;
  project text outside the blocks is never touched.
- Before writing a block: if the project already has its own text for that tool (or a vendor-installed block,
  e.g. from `graphify install` or `omx setup`), skip and report. Never the same rule globally and per project.
- Employer (work-account) rules stay OUT of this repo.

## 3. Agents and harnesses
| Agent | Status | Notes |
|---|---|---|
| Claude Code + oh-my-claudecode | MAIN, configured | signed apt repo on Ubuntu; managed settings: telemetry, error reports, autoupdate off |
| Codex CLI + oh-my-codex | MAIN, configured | npm `--ignore-scripts`; analytics, feedback, update checks off; OMX_AUTO_UPDATE=0; omx block merged with root rules |
| Hermes | configured | non-sudo user; approvals manual; unauthorized DMs ignored; DISCORD_ALLOWED_USERS = owner only (secrets.env); Discord DMs + private #hermes; bot permissions 117760 + Message Content Intent; full GitHub push; Codex login by device code; gateway as user service; skills from official/ only, never --force; daily 09:00 summary; telemetry off |
| herdr | configured | integrations for Claude + Codex; no agent-config surface of its own |
| opencode | always installed | reads AGENTS.md; shared skills dir |
| oh-my-openagent (omo) | OPTIONAL | install only when asked; SUL-1.0 license; audit its pipe-to-bash installer first |
| Gemini CLI, Kimi CLI | ready later | wired when enabled |
| Grok, Kimi, DeepSeek | models only | inside opencode / OMC / OMX; keys in secrets.env |

## 4. MCP servers
| Server | Scope | Settings |
|---|---|---|
| Serena (oraios, GPL-3.0) | global | agent_interface tools (never REPL); excluded_tools [execute_shell_command, serena_repl]; web_dashboard false; SERENA_USAGE_REPORTING=false; --project-from-cwd; contexts claude-code / codex / ide (Hermes); `alwaysLoad: true` in Claude (no deferred tools); trusted_project_path_patterns empty |
| context7 (upstash) | global | local thin-client MCP, docs from context7.com; API key hardcoded (section 13); free plan 1,000 calls/month; fallback after Grounded Docs |
| Grounded Docs (arabold/docs-mcp-server) | global | runs once on the home server, DOCS_MCP_TELEMETRY=false (PostHog is on by default), clients use read-only tools, full-text first, other machines over the private network (port 6280); default for library docs |
| GitHub MCP (github/github-mcp-server) | global | FULL access; token from secrets.env |
| Playwright MCP (microsoft) | per project only | NOT registered at user scope (Claude has no default-off switch for user servers); added per project (`claude mcp add --scope project` / project `.codex/config.toml`) by ai-adopt / ai-start; `--headless --isolated` on servers |
- No extra remote/screen/camera MCPs now (revisit GhostDesk and Mac screen tools in the Mac phase).

### Serena rules (global, owner style; vendor contexts claude-code/codex/ide are the source)
- In a code project, use Serena first to read and edit code. Load its tools before any read, grep or bash on code.
- Read code: get_symbols_overview, then find_symbol with include_body. Read a whole file only if it is a few lines or Serena failed.
- Who uses a symbol: find_referencing_symbols. Edit: replace_symbol_body, insert_before/after_symbol, replace_content for a few lines.
  Do not use built-in Edit on code read with Serena.
- graphify owns discovery (structure, "where is X", Glob/Grep). Serena owns reading and editing code.
- Built-in Read/Edit/Grep are fine for non-code files (md, json, yaml, toml, env, lock files).
- OMC lsp_* and ast-grep tools: fallback only, when Serena fails, or for diagnostics.
- Serena line numbers start at 0. No .git and no .serena: do not use Serena. Serena fails: say so once, then use built-in tools.
- `.serena/`: commit project.yml and memories (reviewed in PRs); gitignore cache/ and project.local.yml (ai-adopt adds this).
- Registry in ~/.serena/serena_config.yml grows per repo, no unregister: ai-doctor reports stale entries.
- Pre-warm language servers per project with `serena project index` (first-use downloads can fail).

### Serena + context7 setup facts (research 6, section 9; full checklists go into ai/rules/serena.md, context7.md)
- Pins: `uv tool install -p 3.13 serena-agent==2.1.0` (release, not main 2.1.1.dev0); `@upstash/context7-mcp@4.6.0` (never @latest).
- Env vars go into each MCP server entry's `env` (SERENA_USAGE_REPORTING=false, CONTEXT7_API_KEY), not only the
  shell, because the client starts the server. Never pass the key as `--api-key` (visible in the process list).
- Register with `serena setup claude-code` / `serena setup codex` (exit 1 if the client is missing); Hermes by hand
  (`--context ide`). Do NOT run `npx ctx7 setup` (would duplicate MCP config, rules and a skill).
- Per machine: `serena init`, edit config keys, `serena download-ls-dependencies <ls>` for used languages.
- Per project: `.serena/` gitignore lines: cache/, project.local.yml, logs/. Verify: `serena tools list`,
  `serena project health-check`, `claude mcp list`, `codex mcp list`, dashboard port 24282 closed.
- `serena_repl` in excluded_tools may be a no-op under the tools interface: harmless, keep it; confirm with `serena tools list`.

### Library docs rules (global, owner style; vendor rule: "use even when you think you know the answer")
- For any library, framework, SDK, API or CLI question, look up docs before writing code.
- Step 1 Grounded Docs: list_libraries, then search_docs with library and project version.
- Step 2 if missing or thin: context7 resolve-library-id, then query-docs, one concept per call.
- Step 3 if both fail: library source or official site, and say docs were not found.
- Use the project's version. No secrets or private code in docs queries (context7 queries leave the machine).
- Not for refactoring, debugging or general programming questions.

## 5. Plugins and skills
Global (every project, always on):
| Tool | Pin | Notes |
|---|---|---|
| Ponytail | 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846 | Claude + Codex; ~/.config/ponytail/config.json = A.3; Codex trusts its 2 hooks once in /hooks |
| i-have-adhd | 1ecea1993b7fce257ffbd686c070948b5e07eda6 | always-on flag files (Claude, opencode; Codex flag path to verify); Hermes: rules appended to SOUL.md; install check: "ADHD MODE ACTIVE (always-on)" |
| graphify (PyPI graphifyy) | 0.9.105 | uv tool shared; `graphify install --platform` per agent; hooks ADVISORY (no --strict); global rule replaces per-project `graphify agents install` |
| RTK | v1.2.0 | built from source on CPUs without AVX2; rtk init for Claude, Codex, Hermes |
| claude-seo | v2.5.0 = 219ff485bb016314bb4c15bfc7978df61c668a4f | all skills on; `/seo setup` once per machine; extensions installers OFF |
| claude-blog | v2.3.2 = 4f9c2cb8fd17f594e868d6c2ce0e8fb2c971f987 | all skills on; notebooklm, image-MCP script, blog-studio, brain OFF |
| mattpocock/skills (copies, pinned commit) | 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d | grilling, grill-me, wait-what, retro, writing-for-agents; no plugin, no `npx skills@latest`; shared ~/.agents/skills + link for Claude |
| oh-my-claudecode, oh-my-codex | pinned at build | main harnesses |
| prompting-claude-and-codex (own skill) | dated snapshot | condensed from official docs, source links |
- caveman: dropped (overlaps i-have-adhd + Reporting style). context7 plugin: dropped (duplicate of the MCP).
- SEO/blog split: one post file = blog-*; site or URL = seo-*. Codex/opencode/Hermes hand SEO and blog work
  to Claude Code (`omc ask claude` / `claude -p`). Context cost accepted: about 9k tokens per session.

Opt-in per project (offered by the ai-adopt / ai-start picker, each with a one-line explanation and warning tag):
- ui-ux-pro-max v2.15.0 = a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5 (never copy its `stack/` folder).
- Playwright MCP.
- llm-wiki-compiler 1.5.0 (costs tokens per compile; if a wiki layer becomes default, pick it or the OMC wiki, not both).
- mattpocock opt-ins: grill-with-docs + domain-modeling + setup-matt-pocock-skills; to-spec, to-tickets,
  triage, wayfinder, implement (auto-commits), implement-spec; prototype; wizard (flipped to user-invoked);
  handoff; teach; to-questionnaire; improve-codebase-architecture + codebase-design (clash with Ponytail);
  ask-matt; code-review (NAME COLLISION with built-in); pr (CONFLICTS with root PR rule); tdd,
  diagnosing-bugs, research (duplicate OMC triggers); misc/* (FROZEN) and in-progress/* (BETA).
  A pick pulls in its callees.
- oh-my-openagent (omo).

## 6. Hooks (global)
- Owner hooks.json (A.2): Notification (permission_prompt|idle_prompt) + Stop -> `~/.dotfiles/bin/claude-notify`;
  SessionStart (startup|resume) -> caffeinate. claude-notify: macOS notification; Linux: Discord #server-info,
  silent no-op without the webhook. Same notify for every agent that supports stop/notification hooks.
- RTK rewrite hook (Claude, Codex, Hermes plugin). On the Mac: never re-enable RTK silently (owner turned it off; ask).
- graphify hook-guard (advisory) on Bash|Grep and Read|Glob, plus compaction reminder.
- herdr status integration hooks.
- Serena: vendor `serena-hooks activate` at SessionStart (Claude, Codex) + `cleanup` at SessionEnd; OWN
  context-only nudge (no deny) on Read/Edit of code files and Bash reads of code paths, 120 s quiet window.
  Vendor `remind` NOT used until its issues #2251 (blocks instead of reminding) and #2204 (false counts) are fixed.
- Docs: context-only nudge on dependency changes (Bash `npm|pnpm|yarn|bun add|install`, `pip install`, `uv add`,
  `cargo add`, `go get`; Edit/Write of package.json, pyproject.toml, requirements*.txt, Cargo.toml, go.mod):
  "look up docs for this library first: Grounded Docs, then context7". PostToolUse on docs tools records
  looked-up libraries so the nudge does not repeat in the session.
- Router hooks (section 7).

## 7. Routing: layered design
One source table, `ai/routing.yaml`, feeds every layer so they never disagree.
| Layer | What | Catches |
|---|---|---|
| L0 | compact routing table in root AGENTS.md | knowledge missing from context (all agents, incl. Hermes) |
| L1 | SessionStart inject + re-inject after compaction | late-session drift, compaction loss |
| L2 | forced-evaluation UserPromptSubmit hook: YES/NO per topic tool, "none needed" option (~+2 s per prompt) | paraphrases, generic wording |
| L3 | deterministic regex fast path (file types, tool names, commands) | exact cases |
| L4 | gates for no-exception rules: audit-before-install, secret-scan, pr-rules (escape hatch documented) | "skipped it and did it anyway" |
| L5 | custom subagents preload needed skills (`skills:`), SubagentStart context | subagent misses |
| L6 | skill descriptions: triggers first, Romanian + Russian phrases, under 1,536 chars | non-English prompts |
| L7 | evals per topic (`claude plugin eval`), local OTel skill_name events, Stop-hook miss log, ai-doctor | silent regressions |
- `type: prompt` hooks only judge or gate, never nudge. Hook commands stay well under the 30 s timeout.
- Avoid triggers that contradict OMC/OMX routing.
- Skill listing budget RAISED (owner): managed setting `skillListingBudgetFraction` ~0.02 so no skill loses its
  description (Claude drops descriptions of least-used skills first when over budget). ai-doctor checks with
  /skill-doctor. Plugin skills cannot be hidden one by one (skillOverrides ignores them).
- Proof of a fired skill reads BOTH paths: PreToolUse/PostToolUse matcher `Skill` (model chose it) and
  UserPromptExpansion (`command_name`, human typed /skill). Gates that check "skill used" read both.
- Hermes: L0 (AGENTS.md in system prompt), L6, and a small `pre_llm_call` plugin for L2/L3 (regex gate +
  "none" option); plugin system-prompt section as L1. Only plain-SKILL.md global skills are copied there
  (Hermes has no manual-only flag); Claude-only packs are handed to `claude -p` (never `--bare`).
- No-em-dash lint after Write/Edit also covers ui-ux-pro-max output (its SKILL.md files contain 34 em dashes).
- Tie-break table (from contracts-skills section 7) goes into routing.yaml: one post file -> blog-*, URL/site
  -> seo-*; "grill me" -> matt grilling, "deep interview" -> OMC deep-interview (kickoff uses grill-me);
  "research" -> OMC research; diff review -> built-in code-review / OMC review; bugs -> OMC debug/trace;
  AGENTS.md/CLAUDE.md/SKILL.md edits -> writing-for-agents; charts -> dataviz; .pptx -> pptx skill;
  "wiki" -> llmwiki only where the project enabled it, else OMC wiki.
- Pins added: mattpocock/skills 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d; llm-wiki-compiler v1.5.0 =
  c9c8734be8a0b854c1547cfa3ee97f0b8c6bfa5f.
- Expected residual misses: about 0% on keyword prompts, 10 to 25% on hard or ambiguous prompts, more for
  non-English, subagents and Hermes. Misses are logged, never silent.
- routing.yaml v2: 25 rules (20 global, 5 opt-in, 3 gates), 25 tie-break rows, `layers` block (L1 re-inject,
  L2 regex-prefiltered with "none" option and 10 s timeout, L4 escape hatch `AI_GATE_SKIP` logged, L7 miss log).
  Browser rule is opt-in (Playwright per project); outside such projects `browser-not-enabled` points to ai-start.
  New nudges: `serena-first` (120 s quiet window) and `docs-on-dependency` (once per library per session).

## 8. Usage contracts (hard requirement)
Every MCP and skill gets `ai/rules/<tool>.md` + routing.yaml rows + evals:
1. Vendor rules: the tool's own recommended CLAUDE.md/AGENTS.md text, verbatim, pinned to the audited version.
2. When to use / when not.
3. Enforcement: layers L0 to L6 that apply and the exact trigger; note what the tool enforces itself.
4. Proof: should-fire and should-not-fire eval prompts (incl. RO/RU) and the signal that it fired.
5. Setup checklist: install + pin per OS; every config file and setting (telemetry/auto-update off); keys
   (required vs optional); one-time per-machine steps (downloads, logins, trust prompts); per-project steps
   (files, .gitignore); verify command; cleanup paths.
- ai-doctor fails if an enabled tool has no contract or its evals fail. install.sh implements every setup item.
- Research running: Serena + context7 (ai-research-6), MCPs/plugins (contracts-mcp), skills (contracts-skills).

## 9. Commands (ai/bin)
- `agent-audit npm|pypi|dir|skill <target>`: guarddog (fails on threat rules only) + osv-scanner + skill-scanner.
- `ai-start`: grill-me -> read routing.yaml -> propose tool set with reasons -> owner confirms -> write project
  config (enabled plugins, .mcp.json, skills, mise.toml + mise.lock, managed AGENTS.md block) -> verify -> commit.
- `ai-adopt`: same project layer for an existing repo; commit "chore(ai): adopt base AI setup vN", show diff,
  one y/N, push; owner's repos only, never third-party; rerun upgrades. A global git template prints a
  non-blocking "no AI base yet, run ai-adopt".
- `ai-doctor`: plugin list/validate, omx doctor, mise ls, skills check, contract presence, evals, miss log.
- `claude-notify`, `pr-resume` (parses the author-sessions block; rebuilt from the owner's note).

## 10. Per-project CLI tools
- mise: `mise.toml` + committed `mise.lock`, `mise install --locked`.

## 11. Toolbox
- `ai/TOOLBOX.md`, stowed to `~/.config/ai/TOOLBOX.md`, not loaded into sessions; one pointer line in AGENTS.md.
- Entries: rea, hypit, MiroFish, thinking-orbs, claude-watch (light intake; full audit before first install).

## 12. Tool intake process (every new tool)
1. Investigate (maintainer, license, release, data it sends). 2. Audit code/installer before anything runs.
3. Overlap check, with how and impact. 4. If added: global wiring + usage contract + verify. 5. Record here.
- Judge the repo's latest audited release for future machines; never rely on what one machine has installed.

## 13. Security and privacy
- Secrets: `~/.config/ai/secrets.env` (600) per machine; MCP configs use `${VAR}`; `secrets.env.example` has names only.
- EXCEPTION (owner): the context7 API key is hardcoded in the repo MCP config and pushed. Free key; worst case
  quota abuse or revocation -> replace in one place. The secret-scan gate allowlists this one key only.
- Local-only paths never committed: `~/.config/claude-seo/`, plugin data dirs, Google OAuth tokens.
- No employer identities or company Google accounts in tool sign-ins.

## 14. Machines
- Home server: test target. `~/.dotfiles` = clone of the `ubuntu-server` branch (built first), `~/.dotfiles-ai`
  = `ai` worktree; its hand-made Phase 5 config is replaced by `~/.dotfiles-ai/install.sh`.
- Macs (this Mac and the older Intel Mac on macOS 12): NOT now (owner 2026-11-11 "No Macs for now").
  When enabled later: after the server test and owner review. Guard rails: never touch the 999 project, its Postgres or
  `com.md999.*` launchd jobs; never re-enable the RTK hook silently.
- Windows: later (chezmoi or a PowerShell script). Its README "AI setup" section says "planned, not supported yet".
- `ubuntu-server` branch (owner: default setup for any new Ubuntu server, with README; the README ends with the
  "AI setup" section): all server phase scripts + notes (power-off recovery, watchdog, no-sleep, WoL,
  disk roles (SSD /, Samsung 500 GB /data main, Hitachi 500 GB /backup mirror, WD 320 GB /mnt/spare320 spare),
  backup times after 07:30 for the 999 crawler, sshd/fail2ban/sysctl hardening of 2026-11-11, Docker 127.0.0.1 ports, Rust coreutils quirks, AVX2 RTK build,
  no desktop, server AGENTS.md hardware section without a git-only line).

## 15. Open items at build
- Serena/context7 open: does --project-from-cwd auto-create .serena/project.yml in a bare git repo (test);
  Codex per-project override of a global `enabled = false` (test; Playwright stays project-only anyway);
  exact graphify always-on wording and block markers.
- Usage contracts for all other tools (contracts-mcp, contracts-skills).
- graphify: per-repo post-commit hook or rule-only; gitignore graphify-out?
- i-have-adhd: which flag path the Codex hook reads.
- omo/omx non-interactive commands for the catalog.
- Claude Code marketplace `ref`/sha pinning syntax; per-skill visibility settings.
- rulesync pilot result.

## 16. Not adopted
superpowers (second kickoff, conflicts with OMC), Docker Dynamic MCP, Smithery (AGPL, hosted), MetaMCP (stale),
Nix tools, per-tool YAML registry, sfw (forced telemetry), context7 On-Premise (paid), LLM classifier router.

## Appendix A: owner blocks, VERBATIM
### A.1 AGENTS.md owner text
```
Lead with the answer. Hard limit: 60 words unless I ask for detail. Tables and lists count. Code blocks do not.

Reporting style
Reports and answers to me use telegraph style. Sacrifice grammar for concision.

Drop articles, filler verbs, and hedging. A fragment is fine. Cost 40/mo, 2h setup, 1 blocker. reads correctly.

Keep facts exact. Never drop a unit, a version, a file path, or a number to save words.

This rule covers status reports and chat answers. Documents, code comments, and technical writing follow the writing style section below.

Writing style
Write technical text with the rules of ASD-STE100 Simplified Technical English. STE is the controlled language that aerospace and defense manufacturers use for maintenance documentation. Its rules make sure that a tired reader who is not a native English speaker cannot misread an instruction.

Write for that tired reader. Each sentence must survive one read.

Code organisation
Before you copy a nearby approach, check it against this file. If they contradict, ask me how to proceed.

Structure code top-down: entry points at the top, implementation details at the bottom.

Put an empty line between logical blocks. Code should read like text with paragraphs.
```
### A.2 hooks.json
```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "permission_prompt|idle_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.dotfiles/bin/claude-notify"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.dotfiles/bin/claude-notify"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "nohup caffeinate -s -w $PPID >/dev/null 2>&1 &"
          }
        ]
      }
    ]
  }
}
```
### A.3 Ponytail config
```json
{
  "defaultMode": "full"
}
```
### A.4 RTK block
```
RTK - Rust Token Killer
Usage: Token-optimized CLI proxy (cuts up to 90% of bash output)

Meta Commands (always use rtk directly)
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk bypass <cmd>      # Execute raw command without filtering (for debugging; `rtk proxy` is a deprecated alias)
rtk pipeline explain  # Show which compression rules fire for an agent/tool/format
rtk pipeline validate # Validate custom pipeline files
Installation Verification
rtk --version         # Should show: rtk 1.x.y (1.0+ required: bypass, pipelines)
rtk gain              # Should work (not "command not found")
which rtk             # Verify correct binary
⚠️ Name collision: If rtk gain fails, you may have reachingforthejack/rtk (Rust Type Kit) installed instead.

Hook-Based Usage
All other commands are automatically rewritten by the Claude Code hook. Example: git status → rtk git status (transparent, 0 tokens overhead)

Since 1.0 the hook also has a gate: a pipeline rule can block or route a command. If a command is refused, run rtk pipeline explain to see the rule.

--ultra-compact was removed in 1.0; do not use it.

Refer to CLAUDE.md for full command reference.
```
### A.5 PR author-sessions note
```
PR author-sessions note
When you create a PR, or push changes to an open PR, keep this hidden block at the end of the PR body, before the generated-with footer:

<!-- author-sessions
updated: <YYYY-MM-DD>
main:   <session-id>  dir: <cwd, with ~ for $HOME>  # <what this session did>
herdr:  <session-id>  dir: <cwd, with ~ for $HOME>  # <what this agent did>
-->
main is your own session. Get the ID with herdr agent get "$HERDR_PANE_ID" | jq -r '.result.agent.agent_session.value'.
Add one herdr line for each Herdr agent that you started or prompted for this PR. Get its ID the same way with its agent name or pane ID, and its dir from .result.agent.cwd.
Do not add subagents. They resume with the main session.
On an update, keep the existing lines, add the new ones, and change updated.
When you edit the PR body for other reasons (for example a recap skill), keep this block.
If an ID is empty, write main: unknown (or herdr: unknown) and tell me. Do not guess an ID.
pr-resume parses this block. Keep the line format exact: one ID, dir:, one path without spaces.
```


## 17. Owner decisions 2026-11-11 (after the plan audit)
- Order: minimal `ubuntu-server` branch first (scripts already run on the server, host values in an untracked
  `host.env`), clone it as `~/.dotfiles` on the server, then the `ai` build and server test.
- House rules: wait for the build (no interim server file). Rules install per user (`~/.config/ai/AGENTS.md`
  imported by each agent); no `/AGENTS.md` or `/etc/claude-code/CLAUDE.md`.
- Distribution: rulesync after an audit and a pilot in a throwaway HOME (on the server; the Macs are out of scope).
- Macs: none for now. Windows README gets a "planned" note.
- Root AGENTS.md size cap: 30 KB (owner raised it from 16 KB). Codex `project_doc_max_bytes` = 65536 so project
  AGENTS.md files still fit. ai-doctor fails above the cap.
- Defaults taken (owner did not object): Linux keeps the systemd-inhibit caffeinate wrapper in SessionStart;
  audit gate blocks npm/pip/uv/npx-latest/curl-to-shell and ASKS for brew, cargo, go, gem, pipx (agent-audit
  cannot scan those yet); secret scanner = gitleaks (pinned, audited); Grounded Docs = a server role in install.sh
  (ufw 6280 from LAN + tailscale0 only); BUILD.md stays untracked (holds local paths).
- Intake audits still owed before the build: oh-my-claudecode, oh-my-codex, opencode (installed always).
- Pending research: project hosting and isolation on the server (rules + tools) feeds the `ubuntu-server` branch
  and an AGENTS.md section.
