# E2: code inventory of the AI setup (branch `ai`)

Audited: a read-only export of `origin/ai` at `f0d8bcd` (2026-11-20), 415 files, 50,361 lines. The local checkout was 2 commits behind and was not used.
Method: line counts with `wc -l`; callers with grep over code (tests and docs apart); dates with `git log -1 --format=%ad --date=short origin/ai -- <path>`; for the function groups of `router.py` and `hooklib.py` the date is the newest `git blame` line in the range.
"dev-mac reaches it" means: with `ai/profiles/dev-mac.env` (the owner's profile on every machine), some installer step, hook event or command can run the code.

Owner decisions used as the yardstick:
- Profile `dev-mac` on every machine. No scanners, no install gate, no root layer (AGENTS.md, Project rules).
- The repo is generic: it names no local project, machine or user.
- Smaller and plug-and-play; hard rules live in checks (git hooks, CI, a small agent hook), not in reminder text.

Verdicts: KEEP, KEEP-SIMPLIFY (what to cut), MERGE-INTO (target), MOVE-OUT (belongs to another branch or repo, mostly the `ubuntu-server` host layer), REMOVE-DEAD (unreachable, proof given), REMOVE-UNUSED-FEATURE (reachable only on profile `server`, which no machine runs), DOC-STALE (text contradicts code).
The "cut" column is the estimated number of lines that go when the verdict is applied (for KEEP-SIMPLIFY: only the named part).


## 0. Inventory


### A. ai/bin

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/bin/agent-audit` | 247 | Scan package, folder or skill before install (guarddog, osv, skill-scanner) | install.sh audit_ok (common.sh:335) only when PROFILE_PACKAGE_AUDIT=1 or a skill-scanner is in PROFILE_SCANNERS; agents-md rule line is `profiles: server`. dev-mac: NOT reached | 2026-11-19 | test_commands (t_agent_audit), test_resolve, test_m3 | **REMOVE-UNUSED-FEATURE** | dev-mac.env: PROFILE_PACKAGE_AUDIT=0, PROFILE_SCANNERS=""; audit_ok returns 0 before `has agent-audit` (common.sh:342-349) | 247 |
| `ai/bin/ai-adopt` | 0 | Symlink to ai-start | owner, ai-update, docs | 2026-11-11 | see ai-start | **KEEP** | symlink, 0 own lines | 0 |
| `ai/bin/ai-check-detect` | 433 | Find a repo's check-fast and check commands per stack | ai-start (SourceFileLoader, ai-start:1288); Makefile block lines | 2026-11-19 | test_tier1 | **KEEP** | dev-mac reached by every ai-adopt | 0 |
| `ai/bin/ai-docs-check` | 179 | Markdown placement, em dash and link checks | ai-check-detect DOCS_LINE/MD_LINE in project `make check`; ai-start --init | 2026-11-17 | test_flow, test_tier1 | **KEEP** | reached by `make check` of every adopted repo; em dash logic duplicates ai-render:35 (list 3) | 0 |
| `ai/bin/ai-doctor` | 1697 | Check machine setup and one project | install.sh do_verify, ai-update, owner | 2026-11-19 | test_cleanup, test_flow, test_m3, test_profiles, test_setup, test_skills, test_tier1 | **KEEP-SIMPLIFY** | cut LINUX/Hermes/box/managed checks: check_claude_policy 716-853 (138), check_hermes+hermes_present+as_hermes 995-1049 (55), check_codex_policy 973-994 (22), check_dropped 691-715 (25), admin_run 135-159 (25), root_owned_chain 575-596 (22), hermes-only mode 68-75, scanner/last30days branches in check_drops_and_defaults 1170-1255; about 340 lines; LINUX is False on dev-mac (ai-doctor:468) | 340 |
| `ai/bin/ai-eval` | 868 | Eval harness: fixtures, install level, behaviour level | owner, verify-ai-setup verify | 2026-11-18 | test_eval, test_skills | **KEEP** | no profile branch (0 server-ish functions) | 0 |
| `ai/bin/ai-evidence-prune` | 132 | Remove committed verify run folders older than N days | owner; named in hooklib verify text | 2026-11-20 | test_commands, test_evidence | **KEEP** | new (2026-11-20), spec docs/specs/verify-evidence-in-git.md | 0 |
| `ai/bin/ai-info` | 283 | List what this machine's setup offers | owner, agents (AGENTS.md Tools line), install.sh links it | 2026-11-17 | test_info | **KEEP-SIMPLIFY** | box/Hermes/server-info lines and a 3rd copy of the plugin id list (ai-info:34-35); about 20 lines | 20 |
| `ai/bin/ai-ledger` | 172 | Regression ledger list, hits and honesty check | project `make check` (LEDGER_LINE, ai-check-detect:48); imports hooklib ledger | 2026-11-14 | test_tier1 | **KEEP** | reached in long-tier repos on dev-mac | 0 |
| `ai/bin/ai-libs` | 792 | Libraries block of AGENTS.md with context7 IDs | ai-start, ai-doctor, knowledge-check nudge text | 2026-11-14 | test_eval, test_info, test_knowledge, test_setup | **KEEP** | core knowledge feature, profile-independent | 0 |
| `ai/bin/ai-playwright-mcp` | 22 | Start the installed Playwright MCP | ai-playwright plugin .mcp.json, ai/mcp/project/playwright.mcp.json | 2026-11-14 | test_resolve, test_commands | **KEEP** | opt-in browser tool | 0 |
| `ai/bin/ai-precommit` | 230 | Lint and verify-commit gate on staged files | git pre-commit hook written by ai-start:1484-1516 | 2026-11-20 | test_eval, test_flow | **KEEP-SIMPLIFY** | gate_skips(env_ok=False) at ai-precommit:60 reads root-owned /etc/ai/gate-skip, never present on dev-mac; about 6 lines | 6 |
| `ai/bin/ai-ratchet` | 241 | Counts that may only improve (tests, skips, lint) | project `make check` RATCHET_LINE (ai-check-detect:46); stop-check.py (server only) | 2026-11-14 | test_knowledge, test_tier1 | **KEEP** | `--only`/`--base` mode exists for stop-check only (could go with it) | 0 |
| `ai/bin/ai-render` | 430 | routing.yaml and agents-md to routing.json, L0.md, AGENTS.md | install.sh base_render, ai-sync, ai-doctor --check | 2026-11-20 | test_commands, test_router, test_skills, test_profiles ... | **KEEP-SIMPLIFY** | profile filter (ai-render:19-21,37,203-228,396) and strength-stop validation become dead with one profile; about 40 lines | 40 |
| `ai/bin/ai-start` | 1799 | Write the project layer into a repo (ai-adopt) | owner, ai-update --projects | 2026-11-20 | test_commands, test_knowledge, test_m3, test_resolve, test_setup, test_skills, test_tier1 | **KEEP-SIMPLIFY** | package_audit_off+audit_passed 1680-1696 (17) dead on dev-mac; no-stop-check writer 1560-1570 feeds the dev-mac-off stop-check; about 30 lines | 30 |
| `ai/bin/ai-sync` | 272 | Re-render and refresh copied rules after a pull | git post-merge hook, install.sh, ai-update | 2026-11-20 | test_commands, test_m3, test_setup, test_tier1 | **KEEP-SIMPLIFY** | root tree trust (136-145), Hermes and admin-layer branches in main 35-91; about 50 lines | 50 |
| `ai/bin/ai-update` | 230 | One command: pull, sync, install, adopt projects | owner | 2026-11-19 | test_tier1 | **KEEP** | plug-and-play entry point (owner rule) | 0 |
| `ai/bin/ai-versions` | 146 | Record tool versions for upgrade-review | install.sh:400, ai-doctor, hooklib upgrade_note | 2026-11-16 | test_flow, test_router | **KEEP** | feeds the upgrade-review session line | 0 |
| `ai/bin/claude-notify` | 0 | Symlink to hooks/claude-notify | install links ~/.local/bin | 2026-11-11 | test_commands | **KEEP** | symlink | 0 |
| `ai/bin/pr-resume` | 137 | Resume the sessions listed in a PR author-sessions block | owner only (no code caller); docs GUIDE:718 | 2026-11-11 | test_commands | **KEEP** | owner command; depends on the author-sessions rule | 0 |

### B. adapters and lib

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `install.sh` | 416 | Installer entry: modes, steps, profile | owner, ai-update | 2026-11-19 | test_setup, test_profiles, test_flow ... | **KEEP-SIMPLIFY** | root branch 57-80, check_mode system, setup_system_target 146-156, run_system 157-172, run_user_part 219-240, first_question 241-257, do_system_layer 328-345, do_hermes 346-355: about 150 lines server-only | 150 |
| `uninstall.sh` | 318 | Undo what install recorded | owner | 2026-11-12 | test_commands, test_m3, test_setup | **KEEP-SIMPLIFY** | undo_system_mode 209-264 (56), undo_system_state 94-110 (17), hermes_state_exists/undo_hermes_state/purge_rel_hermes (16); about 95 lines | 95 |
| `ai/adapters/base.sh` | 527 | Prereqs, pins, links, render, rules, env | install.sh | 2026-11-17 | many | **KEEP-SIMPLIFY** | base_admin_layer 211-233, base_webhook_helper 250-271, base_env_system 492-528 (root_layer only) plus ~/.dotfiles coupling (HOSTING_DOC:10, 138-148, 285): about 110 lines | 110 |
| `ai/adapters/claude.sh` | 1116 | Claude plugins, skills, hooks, permissions, sandbox | install.sh | 2026-11-20 | many | **KEEP-SIMPLIFY** | managed/sandbox (sandbox_prog 930-957, sandbox_excluded, claude_sandbox_json(_final), claude_managed_hooks, claude_managed_policy: 137), claude_box_plugin 548-582 (35), claude_ask_rules+claude_deny_rules 828-877 (50, PROFILE_GUARDS=0), claude_last30days 583-606 (24): about 250 lines | 250 |
| `ai/adapters/codex.sh` | 303 | Codex plugins, skills, hooks, trust, env | install.sh | 2026-11-15 | many | **KEEP-SIMPLIFY** | codex_system_policy 178-205 and codex_system_hooks 206-249 (root_layer, 72) plus box entry in codex_mcp: about 80 lines | 80 |
| `ai/adapters/env.list` | 37 | Telemetry and auto-update env keys | base_env_user, codex_env | 2026-11-18 | many | **KEEP-SIMPLIFY** | opencode lines (3) and SEMGREP for guarddog (1) unused on dev-mac | 4 |
| `ai/adapters/herdr.sh` | 25 | herdr hooks and env | install.sh (pick_agents adds herdr on macOS) | 2026-11-11 | test_flow (t_herdr_picked_on_mac) | **KEEP** | author-sessions herdr lines need it | 0 |
| `ai/adapters/hermes.sh` | 219 | Hermes MCP, skills, hooks, rules, env | install.sh do_hermes only when hermes_exists (common.sh:108 needs root_layer) | 2026-11-15 | test_setup (t_hermes_disabled) | **MOVE-OUT** | PROFILE_ROOT_LAYER=0 on dev-mac; hermes_serena_config 63-76 has 0 callers (REMOVE-DEAD inside) | 219 |
| `ai/adapters/opencode.sh` | 25 | opencode MCP, hooks, env | install.sh want opencode | 2026-11-12 | test_profiles, test_setup | **REMOVE-UNUSED-FEATURE** | profile_agents (install.sh:319-327) strips opencode when PROFILE_OPENCODE=0 | 25 |
| `ai/adapters/tools.sh` | 1100 | Resolve and install every tool | install.sh | 2026-11-18 | many | **KEEP-SIMPLIFY** | tools_scanners 676-728 (53), scanners_drop 729-757 (29), tools_osv_scanner 769-797 (29), tools_opencode 530-556 (27), tools_sandbox_deps 1066-1101 (36), tools_drop_system 1006-1024 (19), agents_drop_system (11), root branches of npm_global/uv/bin_dir/src_swap: about 250 lines | 250 |
| `ai/adapters/linux/apparmor-bwrap` | 15 | AppArmor profile for the sandbox bwrap copy | tools_sandbox_deps (root_layer) | 2026-11-12 | test_setup (t_sandbox_policy) | **MOVE-OUT** | root layer only | 15 |
| `ai/adapters/linux/caffeinate` | 25 | Linux caffeinate shim | nothing: install.sh:341 "no Linux wrapper is installed"; hooks.json runs caffeinate only when uname is Darwin | 2026-11-11 | test_commands, test_setup (string only) | **REMOVE-DEAD** | install.sh:341 comment + hooks.json SessionStart guard `[ "$(/usr/bin/uname -s)" = Darwin ]` | 25 |
| `ai/lib/ai_profile.py` | 57 | Python profile resolver | ai-doctor, ai-info, ai-render, ai-start, stop-check | 2026-11-15 | test_commands, test_setup | **KEEP-SIMPLIFY** | second implementation of profile.sh (list 3); collapses to a 10-line config reader with one profile | 45 |
| `ai/lib/aiconf.py` | 2030 | Merge engine with recorded undo | install, uninstall, ai-sync, ai-start, ai-doctor | 2026-11-17 | test_m3, test_setup | **KEEP-SIMPLIFY** | hermes_config_path+hermes_register 1656-1699 (44), cmd_opencode_mcp 762-808 (47), cmd_codex_managed_hooks 1128-1185 (58): about 150 lines | 150 |
| `ai/lib/common.sh` | 412 | Shell helpers: output, run, root, audit, pins | every shell script | 2026-11-15 | test_commands, test_profiles, test_resolve, test_setup | **KEEP-SIMPLIFY** | run_root, admin_cmd, root_layer, box_present, hermes_* (4), aiconf_root, sudo_ready 154-181, hermes_stage, aiconf_hermes, as_target, root_prepare 242-277, audit_ok body after line 349, audit_accepted 401-413, scan_skipped, skill_scan_off: about 210 lines | 210 |
| `ai/lib/minitoml.py` | 200 | TOML reader for python 3.9 | ai-libs, ai-start | 2026-11-14 | test_knowledge | **KEEP** | macOS /usr/bin/python3 3.9 has no tomllib | 0 |
| `ai/lib/ownertext.py` | 104 | Add-only managed block updates, owner text guard | ai-start, ai-check-detect, aiconf, ai-doctor | 2026-11-17 | test_tier1 | **KEEP** | owner rule: setup updates only add | 0 |
| `ai/lib/profile.sh` | 31 | Shell profile resolver and scanner test | install.sh, ai-sync, agent-audit, common.sh | 2026-11-18 | test_profiles ... | **KEEP-SIMPLIFY** | duplicate of ai_profile.py; exports PROFILE_AUDIT_GATE that nothing reads | 20 |
| `ai/lib/pstack_adapt.py` | 116 | Make our verification skills from pstack upstream | tools.sh pstack_src | 2026-11-18 | test_tier1 | **KEEP** | feeds create-/maintain-verification-skill | 0 |
| `ai/lib/pstack_additions/*.md` | 80 | Our additions to the pstack verification skills | pstack_adapt.py | 2026-11-20 | test_commands, test_skills | **KEEP** | 2 files | 0 |
| `ai/lib/resolve.py` | 768 | Newest stable version per tool | install.sh, tools.sh, ai-start, ai-doctor | 2026-11-15 | test_resolve | **KEEP-SIMPLIFY** | reject/rejected 439-456 (18) only from audit_ok rc=4 (skill-scanner, server) | 18 |
| `ai/lib/root-guard.sh` | 68 | Root never runs code from a user-writable tree | install.sh:67-75, uninstall.sh:48, ai-sync:142 only when id -u = 0 | 2026-11-13 | test_setup | **MOVE-OUT** | dev-mac never runs as root (AGENTS: never sudo; install.sh dies for --for-user without root layer) | 68 |
| `ai/hooks/root/ai-gate-skip` | 33 | Owner escape hatch writer for /etc/ai/gate-skip | install.sh:338 do_system_layer (root_layer) | 2026-11-12 | test_flow, test_info, test_profiles | **MOVE-OUT** | not installed on dev-mac | 33 |
| `ai/hooks/root/ai-webhook-post` | 73 | Root helper that posts to the info webhook | base_webhook_helper (root_layer); claude-notify Linux path | 2026-11-11 | none | **MOVE-OUT** | root layer only, no test | 73 |
| `ai/hooks/hermes/ (__init__.py, plugin.yaml)` | 131 | Hermes plugin that embeds the router | hermes_hooks (do_hermes) | 2026-11-12 | test_commands (t_hermes_plugin) | **MOVE-OUT** | Hermes needs root_layer (common.sh:108) | 131 |
| `ai/audit-accepted.txt` | 22 | Owner-reviewed audit exceptions | common.sh audit_accepted (server path) | 2026-11-15 | test_resolve | **REMOVE-UNUSED-FEATURE** | read only after agent-audit ran, never on dev-mac | 22 |
| `ai/pins.env` | 68 | Tool sources and holds | load_pins, resolve.py | 2026-11-18 | test_resolve | **KEEP-SIMPLIFY** | OPENCODE, OMC_SOURCE (npm CLI route), LAST30DAYS, GUARDDOG, SKILL_SCANNER x2, SCANNER_PYTHON, OSV; LLM_WIKI_SOURCE read by no installer code (REMOVE-DEAD); AI_DROP_* migration lists: about 15 lines | 15 |
| `ai/routing.yaml` | 399 | Routing rows, tie-breaks, winners, skill card | ai-render -> routing.json read by router.py | 2026-11-20 | test_router + 46 case files | **KEEP-SIMPLIFY** | 3 `profiles: [server]` rows (about 25 lines), L4 escape-hatch text, `strength: stop` doc with no stop row, seo/blog/browser prompt regex written twice each: about 45 lines | 45 |
| `ai/mcp/project/playwright.mcp.json` | 8 | Project Playwright MCP entry | ai-start --tools browser | 2026-11-11 | test_resolve | **KEEP** |  | 0 |

### C. plugins (ai/marketplace/plugins)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/marketplace/plugins/ai-box/` | 264 | box MCP server for proj-agent | claude_box_plugin, codex_mcp, hermes_mcp only when PROFILE_BOX=1 and box_present | 2026-11-15 | test_box | **MOVE-OUT** | PROFILE_BOX=0; box_present returns 1 first (common.sh:100) | 264 |
| `ai/marketplace/plugins/ai-core/ (see D, E, F)` | 0 | Router hooks, MCP, one skill | every session | 2026-11-20 | see below | **KEEP-SIMPLIFY** | lines counted in D, E, F | 0 |
| `ai/marketplace/plugins/ai-playwright/` | 14 | Playwright MCP plugin (off at user scope) | project opt-in (ai-adopt --tools browser) | 2026-11-12 | test_commands, test_resolve | **KEEP** |  | 0 |
| `ai/marketplace/plugins/ai-serena/` | 16 | Serena MCP plugin | claude.sh claude_plugins enables it | 2026-11-17 | test_m3 (take over) | **KEEP** |  | 0 |
| `ai/marketplace/.claude-plugin/marketplace.json + .agents/plugins/marketplace.json` | 41 | Marketplace manifests | claude/codex plugin install | 2026-11-15 | test_commands | **KEEP-SIMPLIFY** | drop the ai-box entry | 6 |

### D. ai-core hook files other than router.py and hooklib.py

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai-core/hooks/stop-check.py` | 441 | Run check-fast before Stop; ratchet in long tier | hooks.json and codex-hooks.json run it on every SessionStart and Stop; active_root returns None when PROFILE_GUARDS=0 (stop-check.py:226-227) | 2026-11-18 | test_tier1 (about 266 lines, forces AI_PROFILE=server) | **REMOVE-UNUSED-FEATURE** | dev-mac.env PROFILE_GUARDS=0; both events return before any work | 441 |
| `ai-core/hooks/hooks.json` | 121 | Claude hook wiring | Claude plugin loader | 2026-11-20 | test_setup, test_commands | **KEEP-SIMPLIFY** | 2 stop-check entries; caffeinate entry is macOS-only | 8 |
| `ai-core/hooks/codex-hooks.json` | 104 | Codex hook wiring | Codex plugin loader | 2026-11-19 | test_setup | **KEEP-SIMPLIFY** | 2 stop-check entries | 8 |
| `ai-core/hooks/codex-hooks.managed.json` | 4 | Empty hooks for the root-owned copy | Linux admin installs (/etc/codex/hooks.json) | 2026-11-12 | test_setup (t_codex_managed) | **MOVE-OUT** | root layer only | 4 |
| `ai-core/hooks/claude-notify` | 146 | Desktop or webhook notice when an agent stops | router run_notify (Stop), owner hooks | 2026-11-11 | test_commands, test_setup | **KEEP-SIMPLIFY** | Linux root-helper branch (HELPER /usr/local/sbin/ai-webhook-post) is server-only: about 25 lines | 25 |
| `ai-core/hooks/rtk-hook` | 37 | RTK rewrite, silent in auto mode | Claude PreToolUse (claude_rtk) | 2026-11-17 | test_cleanup | **KEEP** |  | 0 |
| `ai-core/hooks/serena-hook` | 15 | Serena vendor activate/cleanup | hooks.json SessionEnd, codex SessionStart | 2026-11-12 | test_setup | **KEEP** | comment line 4 is stale (list 6) | 0 |
| `ai-core/mcp/ (context7.sh, load-secrets.sh) + .mcp.json + manifests` | 70 | context7 MCP start, secrets loader | plugin .mcp.json | 2026-11-15 | test_resolve | **KEEP** |  | 0 |
| `ai-core/skills/prompting-claude-and-codex/SKILL.md` | 36 | Brief shape for other agents | plugin skill ai-core:prompting-claude-and-codex | 2026-11-11 | test_skills | **MERGE-INTO** | byte-identical to ai/skills/prompting-claude-and-codex/SKILL.md (diff: identical); keep one copy | 36 |

### E. router.py function groups (1974 lines; blame date = newest line in range)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `router.py:1-63 header, imports, constants` | 63 | Docstring, imports, CODE_EXT, SKIP_DIRS, caps | module load | 2026-11-20 | all router tests | **KEEP-SIMPLIFY** | CODE_EXT 54-59 duplicates hooklib.py:2671 (list 3) | 6 |
| `router.py:64-142 entry point (main, plugin_copy, managed_router_present, parse_args)` | 79 | Read hook JSON, dispatch, fail closed | hooks.json command | 2026-11-20 | test_router, _home-folder, test_setup t_managed_router | **KEEP-SIMPLIFY** | managed copy step-aside 68-72 + plugin_copy 111-117 + managed_router_present 118-126 read /etc/claude-code/managed-settings.json, written only by claude_managed_policy (root_layer): about 21 lines | 21 |
| `router.py:143-213 session start + home-folder refusal` | 71 | Status lines, skill card, sessions line, L0 resend | SessionStart | 2026-11-17 | _home-folder, project-knowledge, _skill-card, serena, graph, omc | **KEEP** | dev-mac every session | 0 |
| `router.py:214-311 prompt rules, owner text, notifications, merge OK` | 98 | L3 regex on owner words, tie-breaks, merge word | UserPromptSubmit | 2026-11-18 | diagnosing-bugs, tdd, feature-grill, merge-approval, _tiebreaks | **KEEP** | stop arming at 255-256 is dead with R11 | 0 |
| `router.py:312-385 pre-tool dispatch` | 74 | Gates, skill gates, nudges, deny-once search | PreToolUse | 2026-11-20 | all gate case files | **KEEP** |  | 0 |
| `router.py:386-430 abs_rewrite, excluded_programs` | 45 | Rewrite git push/gh to root-owned absolute path | PreToolUse; needs sandbox.excludedCommands in /etc/claude-code/managed-settings.json | 2026-11-17 | test_setup t_sandbox_policy | **REMOVE-UNUSED-FEATURE** | excluded_programs() returns [] without the managed file; claude_managed_policy writes it only under root_layer (claude.sh:1033-1073) | 45 |
| `router.py:431-523 post-tool, expansion, stop, subagent, end, HANDLERS` | 93 | Skill proof, docs log, nudges after tools, Stop chain | PostToolUse, Stop, SubagentStop, SessionEnd | 2026-11-19 | no-em-dash, ste-sentence, knowledge-check, verify-*, _proof | **KEEP** |  | 0 |
| `router.py:524-664 Ctx and output` | 141 | Decision merge, wall log, JSON output for Claude and Codex | every event | 2026-11-18 | all | **KEEP-SIMPLIFY** | updated_input/updated_decision (abs_rewrite) and the Codex deny text that names sudo ai-gate-skip (636-637): about 10 lines | 10 |
| `router.py:665-697 L2/L3 prompt rendering` | 33 | Forced-eval list of matched rules and tie-breaks | on_user_prompt | 2026-11-12 | _tiebreaks, prompt rules | **KEEP** |  | 0 |
| `router.py:698-767 skill card, skill proof by read, loser reads` | 70 | Card text; SKILL.md reads as proof; Codex loser reads | SessionStart, PostToolUse, Codex PreToolUse | 2026-11-18 | _skill-card, _winners, writing-for-agents | **KEEP** | SKILL_HOMES/SKILL_SOURCES include /opt/agent-plugins (server path) | 0 |
| `router.py:768-817 skill gates (require_skill)` | 50 | Proof check for writing-for-agents and ship | on_pre_tool | 2026-11-19 | writing-for-agents, ship | **KEEP** |  | 0 |
| `router.py:818-841 stop rules (arm_stop_rule, check_stop_rules)` | 24 | Block Stop when an armed skill was not used | on_user_prompt (strength stop), on_stop | 2026-11-18 | diagnosing-bugs, tdd (now nudge cases) | **REMOVE-DEAD** | `grep 'strength: stop' ai/routing.yaml` finds no row (diagnosing-bugs and tdd are `strength: nudge` since ticket 14) | 24 |
| `router.py:842-874 pr-url stop` | 33 | Block a reply that names a PR without its URL | on_stop | 2026-11-19 | pr-url (14 cases) | **KEEP** |  | 0 |
| `router.py:875-974 verify walls` | 100 | verify-tool-exists / verify-tool-used Stop blocks | on_user_prompt, on_stop, on_subagent_stop | 2026-11-18 | verify-tool-exists, verify-tool-used | **KEEP** | loop limits duplicate stop-check (list 3) | 0 |
| `router.py:975-1036 conditions, globs` | 62 | Tool, command and path matching | all rule paths | 2026-11-20 | all | **KEEP** |  | 0 |
| `router.py:1037-1132 navigation, shell content hits, long sentences, nudge key` | 96 | nav proof, em dash in shell writes, STE length | PreToolUse, PostToolUse | 2026-11-19 | nav-first, no-em-dash, ste-sentence | **KEEP** |  | 0 |
| `router.py:1133-1243 project state, opt-in tools, packs, state predicates` | 111 | Which opt-in rows are on in this repo | rule_enabled, check_state | 2026-11-17 | seo, blog, browser, *-not-enabled, tracker-flow, domain-docs | **KEEP-SIMPLIFY** | CLAUDE_PACKS plugin ids are the 5th copy of the list (list 3) | 3 |
| `router.py:1244-1343 graph deny, symbol deny, flags, STATE_PREDICATES` | 100 | Deny first broad search when a graph exists | nav-first rule | 2026-11-19 | nav-first (26 cases) | **KEEP** |  | 0 |
| `router.py:1344-1527 action placeholders` | 184 | Fill {knowledge_index}, {feature_flow} and 12 more | render_action | 2026-11-20 | project-knowledge, feature-grill, verify-before-done, ledger-nudge ... | **KEEP** |  | 0 |
| `router.py:1528-1584 claude_logged_in, skill_paths, claude_handoff` | 57 | How non-Claude agents run claude-seo/blog | {claude_handoff} in seo/blog rows | 2026-11-12 | seo, blog, test_setup t_claude_handoff | **KEEP-SIMPLIFY** | Hermes branch 572-573 and SKILL_SOURCES /opt/agent-plugins are server-only; opencode fallback 580-583 has no agent on dev-mac: about 8 lines | 8 |
| `router.py:1585-1606 docs IDs log` | 22 | Log context7 IDs for ai-libs | PostToolUse on docs MCP tools | 2026-11-17 | test_knowledge | **KEEP-SIMPLIFY** | search_docs/list_versions/scrape branch 597-600 is for Grounded Docs, dropped (routing.yaml:16): REMOVE-DEAD 4 lines | 4 |
| `router.py:1607-1645 run_gate, owner_skip` | 39 | Apply a gate verdict; owner escape hatch | on_pre_tool, every deny path | 2026-11-18 | all gate cases; test_flow owner skip | **KEEP-SIMPLIFY** | owner_skip reads /etc/ai/gate-skip (never installed on dev-mac); `how` text at 1619 checks /usr/local/sbin/ai-gate-skip: about 22 lines | 22 |
| `router.py:1646-1697 winner gate, docs tool test` | 52 | Deny losing OMC/OMX skills | PreToolUse Skill, Codex reads | 2026-11-17 | _winners (24 cases) | **KEEP** |  | 0 |
| `router.py:1698-1777 miss log, transcript events, notify` | 80 | Rule fired but no proof; claude-notify | on_stop | 2026-11-17 | _proof | **KEEP-SIMPLIFY** | run_notify fallback ~/.dotfiles/bin/claude-notify (1767) couples to the base branch | 1 |
| `router.py:1778-1866 SessionState` | 89 | Per-session JSON with flock | every event | 2026-11-11 | all | **KEEP-SIMPLIFY** | quiet_window_s branch 1823-1829: no routing row has quiet_window_s (REMOVE-DEAD 7) | 7 |
| `router.py:1867-1974 helpers, routing load, log rotation` | 108 | Load routing.json, fail-closed marker, small helpers | every event | 2026-11-20 | all | **KEEP-SIMPLIFY** | ROUTING_OVERRIDE (Hermes plugin) 1888-1889 | 3 |

### F. hooklib.py function groups (3253 lines)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `hooklib.py:1-37 docstring, constants, wrappers` | 37 | Shell wrapper tables (sudo, env, rtk ...) | parse_command | 2026-11-18 | all shell cases | **KEEP** |  | 0 |
| `hooklib.py:38-348 shell parsing` | 311 | Tokenize, stages, wrappers, write targets | every shell gate and nudge | 2026-11-19 | all shell cases, test_setup | **KEEP** | core of every gate | 0 |
| `hooklib.py:349-392 gate-skip escape hatch` | 44 | Read root-owned /etc/ai/gate-skip | router owner_skip, ai-precommit:60 | 2026-11-18 | test_setup t_gate_skip_owner_only, test_flow t_vh_commit_gate_owner_skip | **REMOVE-UNUSED-FEATURE** | /etc/ai/gate-skip is written only by ai-gate-skip, installed only in do_system_layer (install.sh:338) | 44 |
| `hooklib.py:393-768 audit-before-install gate` | 376 | Block installs without an agent-audit PASS | row audit-before-install, `profiles: [server]` | 2026-11-12 | cases/audit-before-install.json (66 cases) | **REMOVE-UNUSED-FEATURE** | ai-render:228 drops the row on dev-mac, so GATES['audit-before-install'] is never looked up; audit_status is reached from ai-start only when package audit is on; keep norm_pypi (4 lines, used at 3030) | 372 |
| `hooklib.py:769-1150 secret-scan gate` | 382 | Built-in patterns + gitleaks on commit/push | row secret-scan (dev-mac) | 2026-11-20 | cases/secret-scan.json (60) | **KEEP** | PROFILE_GITLEAKS=1 on dev-mac | 0 |
| `hooklib.py:1151-1491 pr-rules gate` | 341 | PR body fields, fix-PR test, verify run at head | row pr-rules | 2026-11-20 | cases/pr-rules.json (62) | **KEEP** |  | 0 |
| `hooklib.py:1492-1608 merge-approval, no-verify` | 117 | Owner merge word; no --no-verify | rows merge-approval, no-verify | 2026-11-18 | merge-approval (56), no-verify (7) | **KEEP** |  | 0 |
| `hooklib.py:1609-1665 gh-write` | 57 | Ask before gh writes | row gh-write | 2026-11-17 | gh-write (26) | **KEEP** |  | 0 |
| `hooklib.py:1666-1741 no-sudo gate` | 76 | Block sudo/su/doas at a command position | row no-sudo, `profiles: [server]` | 2026-11-15 | cases/no-sudo.json (32), test_setup t_sudo_gate | **REMOVE-UNUSED-FEATURE** | routing.yaml no-sudo `profiles: [server]  # dev-mac (all 3 machines): off` | 76 |
| `hooklib.py:1742-2159 no-destroy gate` | 418 | Block rm -r of data, force push, DROP ... | row no-destroy, `profiles: [server]` | 2026-11-15 | cases/no-destroy.json (101) | **REMOVE-UNUSED-FEATURE** | routing.yaml no-destroy `profiles: [server]  # dev-mac: off`; keep project_tier 1763-1767, cd_target, git_sub, current_branch, short_flags (about 45 lines, used by merge-approval, secret-scan, router, stop-check) | 373 |
| `hooklib.py:2160-2198 worktree-first, GATES tables` | 39 | Deny edits on main in an adopted repo | row worktree-first | 2026-11-20 | worktree-first (7) | **KEEP** | GATES/GATE_PROBES lose 3 entries each | 0 |
| `hooklib.py:2199-2294 regression ledger` | 96 | Parse docs/REGRESSIONS.md, area hits | ledger-nudge, ai-ledger, stop-check | 2026-11-14 | ledger-nudge (7), test_tier1 | **KEEP** |  | 0 |
| `hooklib.py:2295-2477 project skills, session notes (merge review, legacy memory, upgrade, nav)` | 183 | Session-start lines and typed-skill notes | router placeholders | 2026-11-20 | merge-review, legacy-memory, upgrade-review, nav-first | **KEEP** |  | 0 |
| `hooklib.py:2478-2546 verify skill status` | 69 | Find verify-<app>, staleness | router, ai-precommit, ai-doctor | 2026-11-18 | test_tier1, verify-* | **KEEP** |  | 0 |
| `hooklib.py:2547-2665 verify evidence` | 119 | Parse run.log, proof, app code state | verify walls, pr-rules, ai-precommit, verify tool | 2026-11-18 | verify-*, test_verify | **KEEP** |  | 0 |
| `hooklib.py:2666-2912 project knowledge index and delta` | 247 | Map/Libraries status, post-commit delta | project-knowledge, knowledge-check | 2026-11-15 | project-knowledge, knowledge-check, test_setup | **KEEP-SIMPLIFY** | CODE_EXT 2671 duplicates router.py:54 (merge: one copy) | 0 |
| `hooklib.py:2913-3123 graph refresh, libs hits, prompt libs, repo symbol` | 211 | Background graphify, library names in prompt | router PostToolUse, docs-lookup | 2026-11-17 | graph, docs-lookup | **KEEP** |  | 0 |
| `hooklib.py:3124-3253 generic helpers, state, logs` | 130 | project_root, state dir, logs, redact | everything | 2026-11-20 | test_router | **KEEP** |  | 0 |

### G. profile keys (ai/profiles/*.env; dev-mac value / server value)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/profiles/*.env PROFILE_SCANNERS` | 2 | value "" / "guarddog osv-scanner" | profile_has_scanner (profile.sh:31): tools_scanners, scanners_drop, agent-audit, skill_scan_off; ai-doctor:1230 | 2026-11-18 | test_profiles | **REMOVE-UNUSED-FEATURE** | empty on dev-mac: no scanner is installed or run | 2 |
| `ai/profiles/*.env PROFILE_PACKAGE_AUDIT` | 2 | value 0 / 1 | audit_ok (common.sh:342), aud_word, tools_scanners, ai-start package_audit_off | 2026-11-18 | test_profiles | **REMOVE-UNUSED-FEATURE** | 0 on dev-mac: every npm/PyPI audit is skipped | 2 |
| `ai/profiles/*.env PROFILE_AUDIT_GATE` | 2 | value 0 / 1 | nothing: only exported in profile.sh:27 | 2026-11-18 | test_profiles | **REMOVE-DEAD** | no reader in code; the row is switched by routing.yaml `profiles: [server]` (ai-render:228) | 2 |
| `ai/profiles/*.env PROFILE_OPENCODE` | 2 | value 0 / 1 | install.sh profile_agents:320, tools.sh agents_dropped:1029 | 2026-11-18 | test_profiles | **REMOVE-UNUSED-FEATURE** | 0 on dev-mac: opencode stripped and undone | 2 |
| `ai/profiles/*.env PROFILE_LAST30DAYS` | 2 | value 0 / 1 | claude.sh claude_last30days:586, ai-doctor:1231 | 2026-11-18 | test_profiles | **REMOVE-UNUSED-FEATURE** | 0 on dev-mac: plugin uninstalled on each run | 2 |
| `ai/profiles/*.env PROFILE_BOX` | 2 | value 0 / 1 | common.sh box_present:100, claude.sh:550, codex.sh:45, hermes.sh:48, ai-info:72 | 2026-11-18 | test_profiles | **MOVE-OUT** | box is the ubuntu-server host layer | 2 |
| `ai/profiles/*.env PROFILE_ROOT_LAYER` | 2 | value 0 / 1 | common.sh root_layer:97 (32 call sites), ai-doctor LINUX:468 | 2026-11-18 | test_profiles | **MOVE-OUT** | root layer belongs to the server branch | 2 |
| `ai/profiles/*.env PROFILE_GUARDS` | 2 | value 0 / 1 | claude.sh:829,845,889; stop-check.py:213-221; ai-doctor:616 | 2026-11-18 | test_profiles | **REMOVE-UNUSED-FEATURE** | 0 on dev-mac: no ask/deny rules, no Stop check | 2 |
| `ai/profiles/*.env PROFILE_GITLEAKS` | 2 | value 1 / 0 | tools.sh:628 tools_gitleaks; secret-scan gate uses gitleaks when present | 2026-11-18 | test_profiles | **KEEP-SIMPLIFY** | the only key dev-mac turns on: make gitleaks unconditional and drop the key | 0 |
| `ai/profiles/server.env (whole file)` | 11 | Server profile | AI_PROFILE=server, Linux default (ai_profile.py:30, profile.sh:15) | 2026-11-18 | test_profiles, test_router renders --profile server | **MOVE-OUT** | owner: dev-mac everywhere; but the Linux OS default still picks server (profile.sh:15) when ~/.config/ai/profile is missing | 11 |

### H. rules text (ai/rules, copied to ~/.config/ai/rules)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/rules/agents-md-done.md` | 36 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** | Done block contract | 0 |
| `ai/rules/box.md` | 40 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-15 | test_commands (rule files exist) | **MOVE-OUT** | box is server-only | 40 |
| `ai/rules/check-command.md` | 43 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-15 | test_commands (rule files exist) | **KEEP** | check-fast contract | 0 |
| `ai/rules/claude-blog.md` | 41 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** | opt-in pack | 0 |
| `ai/rules/claude-seo.md` | 55 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** | opt-in pack | 0 |
| `ai/rules/context7.md` | 48 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/diagnosing-bugs-stop.md` | 33 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-18 | test_commands (rule files exist) | **DOC-STALE** | file name says stop; routing.yaml diagnosing-bugs is `strength: nudge` (body updated, name not) | 0 |
| `ai/rules/feature-grill.md` | 42 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-15 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/gh-write-gate.md` | 28 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/graphify.md` | 41 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/herdr.md` | 34 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/hermes.md` | 36 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-12 | test_commands (rule files exist) | **MOVE-OUT** | Hermes is root layer only | 36 |
| `ai/rules/i-have-adhd.md` | 37 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/last30days.md` | 43 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **REMOVE-UNUSED-FEATURE** | PROFILE_LAST30DAYS=0 | 43 |
| `ai/rules/llm-wiki-compiler.md` | 35 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **REMOVE-DEAD** | no installer code installs llmwiki; LLM_WIKI_SOURCE in pins.env has no reader | 35 |
| `ai/rules/mattpocock-skills.md` | 40 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-15 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/no-destroy.md` | 53 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **REMOVE-UNUSED-FEATURE** | row is profiles: [server] | 53 |
| `ai/rules/omc.md` | 45 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-19 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/omo.md` | 32 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-11 | test_commands (rule files exist) | **REMOVE-UNUSED-FEATURE** | oh-my-opencode: opencode is off on dev-mac | 32 |
| `ai/rules/omx.md` | 36 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** | Codex | 0 |
| `ai/rules/opencode.md` | 33 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **REMOVE-UNUSED-FEATURE** | PROFILE_OPENCODE=0 | 33 |
| `ai/rules/playwright.md` | 34 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-18 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/ponytail.md` | 43 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/pr-rules.md` | 50 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-19 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/prompting-claude-and-codex.md` | 25 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-12 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/ratchet.md` | 41 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/regression-ledger.md` | 39 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/rtk.md` | 46 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-18 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/serena.md` | 49 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/ship-gate.md` | 28 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/skill-card.md` | 32 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-18 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/stop-check.md` | 53 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **REMOVE-UNUSED-FEATURE** | PROFILE_GUARDS=0 turns stop-check off | 53 |
| `ai/rules/tdd-stop.md` | 29 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-18 | test_commands (rule files exist) | **DOC-STALE** | file name says stop; routing.yaml tdd is `strength: nudge` | 0 |
| `ai/rules/ui-ux-pro-max.md` | 40 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-14 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/verification-skill.md` | 176 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-20 | test_commands (rule files exist) | **KEEP-SIMPLIFY** | 176 lines, 4x the other contracts | 0 |
| `ai/rules/winner-gate.md` | 34 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/writing-for-agents-gate.md` | 34 | rule contract | ~/.config/ai/rules link; AGENTS.md points agents there | 2026-11-17 | test_commands (rule files exist) | **KEEP** |  | 0 |
| `ai/rules/vendor/ (graphify, i-have-adhd, omc, omx, ponytail)` | 522 | Verbatim vendor rule copies at audit time | no code reads them (0 refs) | 2026-11-11 | none | **KEEP-SIMPLIFY** | replace with link + commit hash; omx copy alone is 242 lines | 400 |
| `ai/rules/vendor/pstack-verification/` | 244 | Vendored pstack verification skills | pstack_adapt.py --vendor, tools.sh pstack fallback | 2026-11-11 | test_resolve t_bash_pstack | **KEEP** |  | 0 |

### I. agents-md parts (rendered into ~/.config/ai/AGENTS.md)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/agents-md/00-owner.md` | 27 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-19 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/10-output-shape.md` | 8 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-19 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/20-rtk.md` | 5 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-12 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/30-code-navigation.md` | 11 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-16 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/40-audit-before-use.md` | 13 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-16 | test_commands (em dash, size) | **KEEP-SIMPLIFY** | 4 of 13 lines are `profiles: server` | 4 |
| `ai/agents-md/45-no-root.md` | 4 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-15 | test_commands (em dash, size) | **MOVE-OUT** | every line is `profiles: server` | 4 |
| `ai/agents-md/50-pull-requests.md` | 35 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-19 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/55-git-workflow.md` | 14 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-20 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/60-characters.md` | 4 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-11 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/70-prompting-others.md` | 3 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-12 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/80-tool-catalog.md` | 12 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-16 | test_commands (em dash, size) | **KEEP-SIMPLIFY** | 1 server line | 1 |
| `ai/agents-md/85-l0.md` | 2 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-11 | test_commands (em dash, size) | **KEEP** |  | 0 |
| `ai/agents-md/90-toolbox-and-vendor-rules.md` | 8 | global rule text | ai-render -> AGENTS.md, Codex block | 2026-11-15 | test_commands (em dash, size) | **DOC-STALE** | rendered on dev-mac: "omc (servers; on everywhere on macOS)" and "OMC (on servers only ...)", but dev-mac also runs on Ubuntu dev boxes (dev-mac.env:1) | 0 |

### J. our skills (ai/skills)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/skills/create-verification-skill/` | 269 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-20 | test_skills, test_commands | **KEEP** | made by pstack_adapt | 0 |
| `ai/skills/maintain-verification-skill/` | 71 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-20 | test_skills, test_commands | **KEEP** |  | 0 |
| `ai/skills/promote-skill/` | 26 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-16 | test_skills, test_commands | **KEEP** |  | 0 |
| `ai/skills/prompting-claude-and-codex/` | 36 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-11 | test_skills, test_commands | **KEEP** | keep this copy; the plugin copy merges into it | 0 |
| `ai/skills/release/` | 42 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-18 | test_skills, test_commands | **KEEP** |  | 0 |
| `ai/skills/setup-rollout/` | 161 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-19 | test_skills, test_commands | **KEEP-SIMPLIFY** | EXAMPLES.md and PITFALLS.md describe the owner's three machines ("Main Mac", "Second Mac", "Home server") | 0 |
| `ai/skills/ship/` | 48 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-20 | test_skills, test_commands | **KEEP** | ship gate needs it | 0 |
| `ai/skills/skills-guide/` | 201 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-18 | test_skills, test_commands | **KEEP** | winner table source (test_commands checks it) | 0 |
| `ai/skills/upgrade-review/` | 24 | skill | linked into ~/.claude/skills and ~/.agents/skills | 2026-11-16 | test_skills, test_commands | **KEEP** |  | 0 |

### K. tests (ai/tests)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/tests/run.sh` | 30 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP** | runs 17 files, about 10 min | 0 |
| `ai/tests/test_box.py` | 169 | test file | bash ai/tests/run.sh | 2026-11-15 | - | **MOVE-OUT** | box MCP only (PROFILE_BOX=0) | 169 |
| `ai/tests/test_cleanup.py` | 294 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP** | ticket 03 cleanup; 1 test (t_rtk_managed, 10 lines) is server | 0 |
| `ai/tests/test_commands.py` | 759 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP-SIMPLIFY** | t_agent_audit (50), t_skill_scanner_reject (87), t_hermes_plugin (12) are server-only | 149 |
| `ai/tests/test_eval.py` | 521 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP** |  | 0 |
| `ai/tests/test_evidence.py` | 106 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP** |  | 0 |
| `ai/tests/test_flow.py` | 1040 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP-SIMPLIFY** | t_vh_commit_gate_owner_skip (23) tests /etc/ai/gate-skip | 23 |
| `ai/tests/test_info.py` | 148 | test file | bash ai/tests/run.sh | 2026-11-15 | - | **KEEP** |  | 0 |
| `ai/tests/test_knowledge.py` | 668 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP** |  | 0 |
| `ai/tests/test_m3.py` | 991 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP-SIMPLIFY** | t_last30days (48), t_rejected_sha_cached (22), t_skip_scan (21); caveman/byterover drop tests are one-time migrations | 91 |
| `ai/tests/test_profiles.py` | 380 | test file | bash ai/tests/run.sh | 2026-11-19 | - | **KEEP-SIMPLIFY** | server plan fixtures and server comparisons; with one profile most of the file goes | 216 |
| `ai/tests/test_resolve.py` | 1246 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP-SIMPLIFY** | t_scanners (37), t_osv_scanner (35), t_audit_accept_by_commit (35) | 107 |
| `ai/tests/test_router.py` | 481 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP-SIMPLIFY** | renders routing with `--profile server` (test_router.py:74), so it tests rows dev-mac never loads; switch to dev-mac | 0 |
| `ai/tests/test_setup.py` | 1303 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP-SIMPLIFY** | t_codex_managed (68), t_sandbox_policy (80), t_managed_router (40), t_hermes_disabled (24), t_gate_skip_owner_only (24), t_sudo_gate (28), t_box_registration (15), t_dropped (35) | 314 |
| `ai/tests/test_skills.py` | 242 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP** | checks strength-stop render validation, a dead field | 0 |
| `ai/tests/test_tier1.py` | 1494 | test file | bash ai/tests/run.sh | 2026-11-20 | - | **KEEP-SIMPLIFY** | stop-check block T2 (about 266 lines, forces AI_PROFILE=server) | 266 |
| `ai/tests/test_verify.py` | 127 | test file | bash ai/tests/run.sh | 2026-11-18 | - | **KEEP** |  | 0 |
| `ai/tests/fixtures/profiles/server-linux-all.txt` | 551 | fixture | test_profiles | 2026-11-20 | test_profiles | **REMOVE-UNUSED-FEATURE** | server install plan | 551 |
| `ai/tests/fixtures/profiles/server-linux-user.txt` | 362 | fixture | test_profiles | 2026-11-20 | test_profiles | **REMOVE-UNUSED-FEATURE** | server user plan | 362 |
| `ai/tests/fixtures/profiles/agents-server.md` | 206 | fixture | test_profiles | 2026-11-20 | test_profiles | **REMOVE-UNUSED-FEATURE** | server AGENTS.md render | 206 |
| `ai/tests/fixtures/profiles/devmac-macos-all.txt` | 399 | fixture | test_profiles | 2026-11-20 | test_profiles | **KEEP** | dev-mac plan | 0 |
| `ai/tests/fixtures/profiles/resolved.json` | 347 | fixture | test_profiles | 2026-11-20 | test_profiles | **KEEP** | fixed resolved.json | 0 |

### L. router case files (ai/tests/cases, by rule; lines / cases)

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `ai/tests/cases/audit-before-install.json` | 985 | 66 cases | test_router (server render) | 2026-11-12 | - | **REMOVE-UNUSED-FEATURE** | row is profiles: [server] | 985 |
| `ai/tests/cases/no-destroy.json` | 2264 | 101 cases (protected DB fixture named <db-name>) | test_router (server render) | 2026-11-16 | - | **REMOVE-UNUSED-FEATURE** | row is profiles: [server]; also not generic (list 4) | 2264 |
| `ai/tests/cases/no-sudo.json` | 490 | 32 cases | test_router (server render) | 2026-11-17 | - | **REMOVE-UNUSED-FEATURE** | row is profiles: [server] | 490 |
| `ai/tests/cases/ (43 other files: _home-folder 83/6, _proof 57/5, _skill-card 86/9, _tiebreaks 33/3, _winners 189/24, blog-not-enabled 49/3, blog 34/2, browser-not-enabled 30/2, browser 30/2, diagnosing-bugs 156/20, docs-lookup 222/20, domain-docs 30/2, feature-grill 551/37, gh-write 68/26, graph 70/4, knowledge-check 98/4, ledger-nudge 191/7, legacy-memory 32/3, merge-approval 1228/56, merge-review 34/4, nav-first 204/26, no-ai-base 49/4, no-em-dash 56/8, no-verify 55/7, omc 39/2, pr-rules 1111/62, pr-url 204/14, project-knowledge 109/6, secret-scan 1105/60, seo-not-enabled 49/3, seo 205/9, serena 106/6, ship 63/8, ste-sentence 79/9, tdd 81/10, tracker-flow 108/7, ui 51/5, upgrade-review 36/4, verify-before-done 250/7, verify-tool-exists 261/10, verify-tool-used 195/6, worktree-first 56/7, writing-for-agents 258/42)` | 8001 | cases of rules dev-mac loads | test_router | 2026-11-20 | - | **KEEP** | rows rendered on dev-mac | 0 |

### M. docs

| Unit | Lines | Purpose | Who reaches it (dev-mac?) | Last change | Tests | Verdict | Evidence | Cut |
|---|---|---|---|---|---|---|---|---|
| `README.md` | 577 | doc (52 KB) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | DOC-STALE lines 44, 186, 243 (stop rules), 46/253/556 (ai-gate-skip on dev-mac); overlaps GUIDE | 150 |
| `ai/SPEC.md` | 682 | doc (57 KB) | readers | 2026-11-18 | - | **KEEP-SIMPLIFY** | overlaps GUIDE and the rule contracts; server sections | 200 |
| `ai/SPEC-LOG.md` | 665 | doc (51 KB) | readers | 2026-11-18 | - | **MOVE-OUT** | history only, 0 code refs; archive outside the installed tree | 665 |
| `docs/GUIDE.md` | 2101 | doc (124 KB) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | DOC-STALE lines 589 and 591 (profile keys); 2101 lines is the largest file in the repo | 700 |
| `docs/TOOLS.md` | 417 | doc (52 KB) | readers | 2026-11-18 | - | **KEEP-SIMPLIFY** | server tools (box, Hermes, scanners, opencode, last30days) | 100 |
| `docs/AUDIT-BRIEF.md` | 348 | doc (26 KB) | readers | 2026-11-17 | - | **MOVE-OUT** | brief for a past audit; belongs in docs/reports or history | 348 |
| `docs/ACCEPTANCE.md` | 151 | doc (16 KB) | readers | 2026-11-19 | - | **KEEP** |  | 0 |
| `docs/AGENTS-MD.md` | 185 | doc (13 KB) | readers | 2026-11-18 | - | **KEEP** |  | 0 |
| `docs/CONTEXT.md` | 151 | doc (14 KB) | readers | 2026-11-19 | - | **KEEP** | glossary of commands | 0 |
| `docs/EXTENDING.md` | 186 | doc (18 KB) | readers | 2026-11-19 | - | **KEEP** |  | 0 |
| `docs/INSTALL.md` | 159 | doc (17 KB) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | server install part | 40 |
| `docs/SECURITY.md` | 76 | doc (8 KB) | readers | 2026-11-19 | - | **KEEP-SIMPLIFY** | sandbox and box claims are server-only | 20 |
| `docs/REGRESSIONS.md` | 29 | doc (8 KB) | readers | 2026-11-20 | - | **KEEP** |  | 0 |
| `docs/agents/notes.md` | 30 | doc (2 KB) | readers | 2026-11-18 | - | **KEEP** |  | 0 |
| `ai/marketplace/plugins/ai-core/hooks/README.md` | 252 | doc (24 KB) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | gate list includes server gates and the escape hatch | 60 |
| `ai/TOOLBOX.md` | 40 | doc (3 KB) | readers | 2026-11-11 | - | **KEEP** |  | 0 |
| `docs/tickets/ (64 files)` | 1023 | doc (-) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | verify-enforcement 08-<project-c>-pilot, 09-<project-b>, 10-<project-d> name local projects | 35 |
| `docs/maps/ (9 files)` | 228 | doc (-) | readers | 2026-11-19 | - | **KEEP** |  | 0 |
| `docs/reports/ (5 files)` | 522 | doc (-) | readers | 2026-11-19 | - | **KEEP** |  | 0 |
| `docs/research/ (2 files)` | 303 | doc (-) | readers | 2026-11-20 | - | **KEEP** |  | 0 |
| `docs/specs/ (4 files)` | 380 | doc (-) | readers | 2026-11-20 | - | **KEEP** |  | 0 |
| `.verify/evidence/ (5 runs, 40 files)` | 1955 | doc (-) | readers | 2026-11-20 | - | **KEEP-SIMPLIFY** | committed by design (spec verify-evidence-in-git); state.json files hold /Users/<owner> paths; ai-evidence-prune keeps it short | 0 |
| `.agents/skills/verify-ai-setup/ (16 files)` | 1227 | doc (-) | readers | 2026-11-20 | - | **KEEP** | the repo's own verify tool | 0 |
| `ai/evals/ (33 files)` | 638 | doc (-) | readers | 2026-11-18 | - | **KEEP-SIMPLIFY** | last30days.md (6) unused; mattpocock-and-llmwiki.md (10) half dead | 16 |
| `secrets.env.example` | 32 | doc (1 KB) | readers | 2026-11-11 | - | **KEEP** |  | 0 |

## 1. Totals

Lines of the units that carry each verdict (left), and the lines that go when the verdicts are applied (right, "cut").

| Verdict | Code lines | Code cut | Test lines | Test cut | Doc lines | Doc cut |
|---|---|---|---|---|---|---|
| KEEP | 7245 | 0 | 10883 | 0 | 5555 | 0 |
| KEEP-SIMPLIFY | 13743 | 2060 | 7694 | 1166 | 8764 | 1726 |
| MERGE-INTO | 36 | 36 | 0 | 0 | 0 | 0 |
| MOVE-OUT | 822 | 822 | 169 | 169 | 1093 | 1093 |
| REMOVE-DEAD | 51 | 51 | 0 | 0 | 35 | 35 |
| REMOVE-UNUSED-FEATURE | 1704 | 1655 | 4858 | 4858 | 214 | 214 |
| DOC-STALE | 0 | 0 | 0 | 0 | 70 | 0 |
| **Sum** | 23601 | 4624 | 23604 | 6193 | 15731 | 3068 |

Notes on the totals:
- Code = shell, Python, JSON wiring, routing.yaml, pins.env, profile keys. Tests = `ai/tests` (files, fixtures, case files). Docs = rules, agents-md parts, skills, docs, evals, `.verify`, `.agents`.
- KEEP-SIMPLIFY counts the whole unit on the left and only the named part as cut. MOVE-OUT counts as cut because the lines leave this branch.

### The hook router after every REMOVE verdict

| File | Now | After REMOVE-DEAD and REMOVE-UNUSED-FEATURE only | After also the KEEP-SIMPLIFY cuts (managed copy, owner_skip, Hermes bits) |
|---|---|---|---|
| `router.py` | 1974 | 1894 (abs_rewrite 45, stop rules 24, Grounded Docs branch 4, quiet_window 7) | about 1820 |
| `hooklib.py` | 3253 | 2388 (gate-skip 44, audit 372, no-sudo 76, no-destroy 373) | about 2380 (CODE_EXT copy) |
| `stop-check.py` | 441 | 0 | 0 |
| **Sum** | **5668** | **4282** | **about 4200** |

The remaining 4,282 lines hold the 6 gates that dev-mac renders: secret-scan, pr-rules, merge-approval, no-verify, gh-write, worktree-first. They also hold 2 skill gates, the winner gate, 3 Stop walls and about 20 nudges. The shell parser (311 lines) stays: every gate needs it.

## 2. Reachable with profile dev-mac versus server-only

Every row below is unreachable on dev-mac. Proof: the profile key or the routing row named.

| Server-only unit | Lines | Switch |
|---|---|---|
| `hooklib.py:393-768` audit-before-install gate | 376 | routing row `profiles: [server]` |
| `hooklib.py:1666-1741` no-sudo gate | 76 | routing row `profiles: [server]` |
| `hooklib.py:1742-2159` no-destroy gate (minus 45 shared lines) | 373 | routing row `profiles: [server]` |
| `hooklib.py:349-392` gate-skip escape hatch + `router.py:1607-1645` owner_skip part | 66 | `ai-gate-skip` installed only by `do_system_layer` |
| `router.py:64-142` managed copy step-aside part | 21 | `/etc/claude-code/managed-settings.json` (root layer) |
| `router.py:386-430` abs_rewrite | 45 | same managed file |
| `router.py` Hermes bits (handoff branch, ROUTING_OVERRIDE) | 11 | Hermes needs root layer |
| `stop-check.py` | 441 | `PROFILE_GUARDS=0` |
| `ai/bin/agent-audit` | 247 | `PROFILE_PACKAGE_AUDIT=0`, `PROFILE_SCANNERS=""` |
| `ai/audit-accepted.txt` | 22 | same |
| `ai/lib/root-guard.sh` | 68 | only as root |
| `ai/lib/common.sh` root, Hermes, box, audit helpers | about 210 | `root_layer`, `PROFILE_BOX`, `PROFILE_PACKAGE_AUDIT` |
| `ai/lib/aiconf.py` Hermes and Codex managed hooks | about 102 | root layer |
| `ai/lib/resolve.py` reject records | 18 | skill-scanner REJECT only |
| `ai/adapters/hermes.sh` | 219 | `hermes_exists` needs `root_layer` |
| `ai/hooks/hermes/` | 131 | same |
| `ai/hooks/root/ai-gate-skip`, `ai-webhook-post` | 106 | `do_system_layer`, `base_webhook_helper` |
| `ai/adapters/linux/apparmor-bwrap` | 15 | `tools_sandbox_deps` (root layer) |
| `ai/adapters/claude.sh` managed sandbox, managed hooks, box plugin, ask/deny rules, last30days | about 250 | root layer, `PROFILE_BOX`, `PROFILE_GUARDS`, `PROFILE_LAST30DAYS` |
| `ai/adapters/codex.sh` system policy and hooks, box entry | about 80 | root layer, `PROFILE_BOX` |
| `ai/adapters/base.sh` admin layer, webhook helper, /etc env | about 82 | root layer |
| `ai/adapters/tools.sh` scanners, osv, sandbox deps, system drops, opencode | about 250 | `PROFILE_SCANNERS`, root layer, `PROFILE_OPENCODE` |
| `ai/adapters/opencode.sh` | 25 | `PROFILE_OPENCODE=0` |
| `install.sh` system mode, root guard block, first_question, do_system_layer, do_hermes | about 150 | `--for-user`, root layer |
| `uninstall.sh` system and Hermes undo | about 95 | same |
| `ai/bin/ai-doctor` LINUX, Hermes, box, scanner checks | about 340 | `LINUX` is False on dev-mac (ai-doctor:468) |
| `ai/bin/ai-sync` root tree and admin branches | about 50 | root layer |
| `ai-core/hooks/claude-notify` Linux root helper branch | about 25 | root helper only on the server |
| `ai-core/hooks/codex-hooks.managed.json` | 4 | root layer |
| `ai/marketplace/plugins/ai-box/` | 264 | `PROFILE_BOX=0` |
| `ai/profiles/server.env` | 11 | owner: dev-mac everywhere |
| agents-md lines with `<!-- profiles: server -->` | 9 | ai-render drops them |
| rules: box, hermes, no-destroy, stop-check, last30days, opencode, omo | 290 | the matching keys |
| **Sum (code + rules)** | **about 4,580** | |

Tests and fixtures that exist only for these units:

| Test or fixture | Lines |
|---|---|
| `ai/tests/cases/no-destroy.json` | 2264 |
| `ai/tests/cases/audit-before-install.json` | 985 |
| `ai/tests/cases/no-sudo.json` | 490 |
| `ai/tests/fixtures/profiles/server-linux-all.txt`, `server-linux-user.txt`, `agents-server.md` | 1119 |
| `ai/tests/test_box.py` | 169 |
| `ai/tests/test_setup.py`: t_codex_managed, t_sandbox_policy, t_managed_router, t_hermes_disabled, t_gate_skip_owner_only, t_sudo_gate, t_box_registration, t_dropped | 314 |
| `ai/tests/test_tier1.py` stop-check block (forces `AI_PROFILE=server`, test_tier1.py:318, 788) | about 266 |
| `ai/tests/test_profiles.py` server plan parts | about 216 |
| `ai/tests/test_commands.py`: t_agent_audit, t_skill_scanner_reject, t_hermes_plugin | 149 |
| `ai/tests/test_resolve.py`: t_scanners, t_osv_scanner, t_audit_accept_by_commit | 107 |
| `ai/tests/test_m3.py`: t_last30days, t_rejected_sha_cached, t_skip_scan | 91 |
| `ai/tests/test_flow.py`: t_vh_commit_gate_owner_skip | 23 |
| **Sum** | **about 6,190** |

Important: `ai/tests/test_router.py:74` renders the routing with `--profile server`. So the main router suite runs rows that no machine loads, and it never runs the dev-mac render.

## 3. Duplicated logic

1. **Profile resolution, two implementations with different orders.** `ai/lib/profile.sh:7-30` (flag > file > OS default) and `ai/lib/ai_profile.py:17-30` (env `AI_PROFILE` > file > OS default). Both default Linux to `server` (`profile.sh:15`, `ai_profile.py:30`), which contradicts "dev-mac everywhere".
2. **Profile defaults = server values, written at each read.** `${PROFILE_X:-1}` or `.get("PROFILE_X", "1")`: `common.sh:97,100,342`, `install.sh:320`, `tools.sh:32,694,1029`, `claude.sh:550,586,829,845,889`, `codex.sh:45`, `hermes.sh:48`, `ai-doctor:468,616,1230,1231`, `stop-check.py:219`, `ai-start:1685`, `ai-info:72`, `profile.sh:31`, `agent-audit:33,37`. A missing key turns a server feature on.
3. **"Is this project adopted", two markers.** `.ai/enabled`: `router.py:888`, `router.py:1376`, `hooklib.py:2839`, `stop-check.py:231`, `ai-doctor:1525`. `.ai/base-version`: `router.py:1222`, `ai-info:147`, `ai-update:170`.
4. **`.ai/enabled` parsing.** `router.py:1158-1162` (enabled_tools), `hooklib.py:2754-2769` (enabled_ids), `hooklib.py:2305-2316` (project_skills), `stop-check.py:231-235`, `ai-info:140`, `ai-start:127`.
5. **Em dash checks (6 places).** routing row `no-em-dash` (`routing.yaml:207-212`) with `router.py:1045-1073`; `ai-docs-check:122-144`; `ai-render:35,65,94`; `ai-doctor:210`; `pstack_adapt.py:29`; `test_commands.py:110`. Plus the agent-side hook named in AGENTS.md.
6. **Claude plugin id lists (claude-seo, claude-blog).** `router.py:1168-1169`, `ai-start:549`, `ai-info:34-35`, `ai-doctor:802`, `pins.env:68`, `claude.sh:519-520`. Our own ids: `router.py:200` (PROJECT_PLUGINS) and `claude.sh:534-535`.
7. **Code file extensions.** `router.py:54-59` (CODE_EXT, is_code_path 1003) and `hooklib.py:2671` (CODE_EXT, is_code_file 2688).
8. **Shell tool names.** `router.py:52` (SHELL_TOOLS) and the string `Bash|shell|exec_command|local_shell` in `routing.yaml:83,119,127,142,156,164,187,195,210`; hook matchers in `hooks.json` and `codex-hooks.json` (Codex: `Bash|apply_patch` only).
9. **Navigation tool names.** `router.py:1033` (NAV_TOOLS) and the nav-first proof regex `routing.yaml:88` (the code comment says "keep in step").
10. **Loop limits for Stop blocks.** `router.py:883-884` (VERIFY_MAX_TRIES/CHAIN) and `stop-check.py:45-46` (MAX_TRIES/MAX_CHAIN).
11. **Prompt regexes written twice.** SEO `routing.yaml:252` and `:307`; blog `:260` and `:316`; browser `:268` and `:325`.
12. **Managed block markers.** `aiconf.py:376-377` (`<!-- AI:<name> vN START -->`), `ownertext.py` (owner text inside blocks), OMC markers in `base.sh:298-313` and `tools.sh:497`.
13. **Projects folder default `~/work`.** `ai-update:188-191` and `base.sh:321-329`.
14. **claude-notify location.** `ai/bin/claude-notify` symlink, `base.sh:138-148` (links `~/.dotfiles/bin/claude-notify`), `router.py:1765-1767` (fallback path).
15. **Skill file.** `ai/skills/prompting-claude-and-codex/SKILL.md` and `ai-core/skills/prompting-claude-and-codex/SKILL.md` are byte-identical.

## 4. Not generic

| Group | Value | Where | Single home |
|---|---|---|---|
| Local projects | `<db-name>` (protected DB) | `ai/tests/cases/no-destroy.json:756-1489` (about 25 places) | test fixture name `appdb` |
| Local projects | <project-c> | `ai/tests/test_flow.py:351,772,782`; `test_tier1.py:280,397`; `cases/verify-tool-used.json:5`; `ai/bin/ai-start:370`; `docs/tickets/verify-enforcement/08-<project-c>-pilot.md` | neutral names |
| Local projects | <project-b> | `ai/bin/ai-check-detect:184`; `ai/tests/test_tier1.py:56`; `docs/tickets/verify-enforcement/09-<project-b>.md` | neutral names |
| Local projects | <project-d> | `docs/tickets/verify-enforcement/10-<project-d>.md` | move to the owner's notes |
| Machine | `<server>` | `ai/tests/test_setup.py:568,571,1191,1209` | fixture user `agent` |
| Machine | three machines ("Main Mac", "Second Mac", "Home server") | `ai/skills/setup-rollout/EXAMPLES.md:3-15`, `PITFALLS.md:7` | owner-local notes |
| User | `/Users/<owner>/...` paths | `.verify/evidence/*/state.json` (8 lines each, 5 runs), `01-cli.txt` | run paths relative to the repo |
| OS path | `/usr/bin/python3` | `hooks.json` (10), `codex-hooks.json` (9), `ai-doctor:868-872,1291,1622` | `AI_PYTHON` in config, rendered into the hook files |
| OS path | `/opt/ai-setup` | `install.sh:4-6,63-64`, `common.sh:86`, `ai-doctor:725` | server branch |
| OS path | `/etc/ai/gate-skip`, `/usr/local/sbin/ai-gate-skip` | `hooklib.py:355`, `router.py:1619`, `install.sh:338` | server branch |
| OS path | `/etc/claude-code/managed-settings.json` | `router.py:384`, `ai-doctor:470` | server branch |
| OS path | `/etc/server/webhooks/*.url` | `base.sh:247-255`, `ai/hooks/root/ai-webhook-post` | server branch |
| OS path | `/run/proj-agent.sock`, `/usr/local/sbin/proj-agent` | `common.sh:93-94` | server branch |
| OS path | `/opt/agent-plugins` | `router.py:1530` (SKILL_SOURCES) | server branch |
| User name | `HERMES_USER=hermes` | `common.sh:16`, `ai-doctor:473` | server branch |
| Owner layout | `~/.dotfiles` base branch | `base.sh:10,138-148,285`, `router.py:1767`, `claude-notify:5`, `install.sh:248` | `AI_BASE_DIR` in config |
| Owner layout | `~/work` projects folder | `ai-update:191`, `base.sh:329` | `AI_PROJECTS_DIR` in config (file `projects-dir` exists already) |
| OS | macOS `caffeinate` SessionStart hook | `hooks.json` SessionStart entry 2 | opt-in key |
| Language | Romanian and Russian prompt words | `routing.yaml` diagnosing-bugs, tdd, feature-grill triggers; `hooklib.py:1494-1511` (merge words); skill descriptions (`ship`: "gata", "готово"; `release`: "lansare", "релиз"); `ai/evals/HOWTO.md:4,27` | `AI_PROMPT_LANGS=en,ro,ru` plus one regex pack file per language |
| GitHub accounts | `claude-seo@agricidaniel-claude-seo`, `claude-blog@agricidaniel-blog` | 6 code places (list 3, item 6) | `pins.env` only, others read it |
| GitHub | owner allow list from the origin of `~/.dotfiles-ai` | `ai-start:1710-1721` (reads `~/.config/ai/config.env`) | already generic |

Today the owner's values sit in 5 files: `~/.config/ai/profile`, `~/.config/ai/projects-dir`, `~/.config/ai/config.env` (AI_GITHUB_OWNERS), `~/.config/ai/secrets.env`, `~/.config/ai/webhooks/info.url`. One file can hold them all: `~/.config/ai/config.env` (KEY=VALUE, one shell reader and one Python reader). Keys: `AI_PROJECTS_DIR`, `AI_GITHUB_OWNERS`, `AI_PROMPT_LANGS`, `AI_BASE_DIR`, `AI_PYTHON`, `AI_NOTIFY` (macos, webhook, none), `AI_KEEP_AWAKE`. The repo would ship `ai/config.defaults.env` with generic defaults. Secrets stay in `secrets.env`.

## 5. The 15 changes with the best ratio of removed lines to risk

Ranked. "Removed" is code + tests + docs.

| # | Change | Files | Lines removed | What could break | Test that catches a break |
|---|---|---|---|---|---|
| 1 | Delete the no-destroy gate | `hooklib.py:1742-2159` (keep project_tier, cd_target, git_sub, current_branch, short_flags), `cases/no-destroy.json`, `rules/no-destroy.md`, routing row, GATES/GATE_PROBES entries | about 2,700 | the 5 shared helpers (merge-approval, secret-scan, ledger, router placeholders use them) | `test_router` cases merge-approval (56), secret-scan (60), ledger-nudge; `test_tier1` |
| 2 | Delete the audit-before-install gate and agent-audit | `hooklib.py:393-768` (keep norm_pypi), `cases/audit-before-install.json`, `ai/bin/agent-audit`, `common.sh` audit_ok body after line 349 and audit_accepted, `ai/audit-accepted.txt`, `ai-start:1680-1696`, routing row, 2 agents-md lines | about 1,750 | `audit_ok` callers in `tools.sh` and `claude.sh` must keep a pass-through; ai-start Playwright install path | `test_resolve` (t_playwright_profile_audit, t_bash_plugin_clone), `test_profiles` dev-mac plan fixture |
| 3 | Delete the no-sudo gate | `hooklib.py:1666-1741`, `cases/no-sudo.json`, `agents-md/45-no-root.md`, routing row, `test_setup.py` t_sudo_gate | about 610 | nothing on dev-mac; keep the sudo entry of WRAPPERS_WITH_VALUES (parser) | `test_router` shell cases of the other gates |
| 4 | Drop profile `server` and its fixtures; make dev-mac the only behaviour | `ai/profiles/server.env`, 3 server fixtures, server parts of `test_profiles.py`, `ai-render` profile filter, `profile.sh`/`ai_profile.py` collapse | about 1,450 | the Linux OS default (`profile.sh:15`, `ai_profile.py:30`) picks server today: change it first; `test_router.py:74` renders `--profile server` | `test_profiles` t_devmac_plan, t_devmac_linux_plan; `test_router` after the switch to dev-mac |
| 5 | Delete stop-check | `stop-check.py`, 2 entries each in `hooks.json` and `codex-hooks.json`, `rules/stop-check.md`, `test_tier1.py` T2 block, no-stop-check writer `ai-start:1560-1570`, `ai-ratchet --only/--base` mode | about 800 | Codex hook trust hashes change (a new trust after install); `ai-doctor:523` regex | `test_setup` t_codex_trust (hook count at `test_setup.py:177`), `test_tier1` adopt tests |
| 6 | Archive the history docs | `ai/SPEC-LOG.md`, `docs/AUDIT-BRIEF.md` | 1,013 | relative links to them | `ai-docs-check --md` (link check) |
| 7 | Remove dead bits | `linux/caffeinate`, `hermes_serena_config`, `rules/llm-wiki-compiler.md` + `LLM_WIKI_SOURCE`, PROFILE_AUDIT_GATE (2 env files + export), Grounded Docs branch `router.py:597-600`, quiet_window branch `router.py:1823-1829` | about 90 | none found by grep | `test_commands`, `test_knowledge` (log_docs_ids), `test_setup` |
| 8 | Remove the stop-rule machinery | `router.py:818-841`, arm call `:255-256`, `ai-render` strength-stop checks, stop text in README 186, 243 | about 70 | an owner who later wants a stop rule back | `test_router` diagnosing-bugs and tdd cases, `test_skills` |
| 9 | Move Hermes out | `hermes.sh`, `ai/hooks/hermes/`, Hermes parts of aiconf, common.sh, ai-doctor, uninstall, router, `rules/hermes.md`, 2 tests | about 580 | `install.sh` do_hermes and `ai-sync` Hermes branches | `test_setup`, `test_commands`, `ai-doctor --quick` |
| 10 | Move the box out | `ai-box/`, `test_box.py`, `rules/box.md`, `claude_box_plugin`, box parts of codex.sh, hermes.sh, common.sh, marketplace entry, ai-doctor | about 550 | marketplace listing; a machine that once had `ai-box@ai` | `test_setup` t_box_registration, `test_commands` plugin list |
| 11 | Remove the scanners | `tools_scanners`, `scanners_drop`, `tools_osv_scanner`, `profile_has_scanner`, resolve reject, `--skip-scan` flag, 6 pins, 5 tests | about 380 | install.sh usage text; old scanner copies on machines stay (scanners_drop is their cleanup) | `test_resolve`, `test_m3`, `test_profiles` |
| 12 | Remove the gate-skip escape hatch | `hooklib.py:349-392`, `router.py` owner_skip and `how` text, `ai-precommit:60`, `ai/hooks/root/ai-gate-skip`, 2 tests, README and GUIDE lines | about 200 | every deny message text; Codex deny text `router.py:636-637` | `test_router` (deny texts), `test_flow` commit gate tests |
| 13 | Remove opencode and omo | `opencode.sh`, `tools_opencode`, `aiconf cmd_opencode_mcp`, `rules/opencode.md`, `rules/omo.md`, env.list lines, pin | about 190 | `agents_drop_user` cleanup of old opencode installs | `test_profiles`, `test_setup` |
| 14 | Remove last30days | `claude_last30days`, `rules/last30days.md`, `evals/last30days.md`, `test_m3` t_last30days, ai-doctor branch, pin, agents-md line | about 135 | the uninstall of an old copy on a machine that still has it | `test_m3`, `test_profiles` t_devmac_last30days |
| 15 | Move the managed-settings and sandbox root layer out | router managed parts (76), claude.sh managed/sandbox (137), codex.sh system (72), base.sh admin/env (82), tools_sandbox_deps + apparmor (51), codex-hooks.managed.json, ai-doctor policy checks (about 180), 3 tests (188) | about 800 | many files at once; ai-doctor checks on dev-mac must not fail when the code goes | `test_setup`, `ai-doctor --quick` on dev-mac, `test_router` _home-folder |

## 6. Docs versus code

Promises the code does not keep (or text that contradicts it):

1. `README.md:44`: "**Stop rules:** diagnosing-bugs and tdd." Code: `routing.yaml` diagnosing-bugs `strength: nudge   # ticket 14 (2026-11-18): as a stop, 6 of 6 blocks were false`; tdd is `strength: nudge` too.
2. `README.md:186`: "Stop rules make the agent use a skill before it ends a turn." and `README.md:243`: "Stop rules (strength `stop`): the prompt arms the rule ..." Code: no routing row has `strength: stop`.
3. `README.md:556`: "Only the owner can open a gate: `sudo ai-gate-skip <gate> <minutes> <why>`." (also 46, 253). Code: `install.sh:338` installs ai-gate-skip only in `do_system_layer` (root layer); on dev-mac `router.py:1619` says "by running the command".
4. `docs/GUIDE.md:589`: "| PROFILE_AUDIT_GATE | 0 | No audit-before-install gate |". Code: no reader of PROFILE_AUDIT_GATE; the row goes because of `profiles: [server]` (`ai-render:228`).
5. `docs/GUIDE.md:591`: "PROFILE_GUARDS | 0 | ... no-sudo and no-destroy rows off". Code: those rows are dropped by `profiles: [server]`, not by PROFILE_GUARDS.
6. `ai/profiles/dev-mac.env:1`: "skill-scanner is the only scanner". Same file, line 8: `PROFILE_SCANNERS=""`.
7. `ai/lib/common.sh:341`: "plugin sources (dir, skill) are still scanned: skill-scanner only there". Code: `skill_scan_off` (common.sh:333) is true on dev-mac, so `audit_ok` says "not scanned" and returns 0.
8. `ai/bin/agent-audit:13`: "PASS-SKILL: skill-scanner only, profile dev-mac". Code: dev-mac has no skill-scanner.
9. `ai-core/hooks/serena-hook:3-4`: "the router's serena-first nudge replaces it". Code: `routing.yaml:15` "Removed ... serena-first"; no such row.
10. `routing.yaml:16`: "Serena and graphify are opt-in per project." Same file, `:274`: "serena and graph are ON BY DEFAULT".
(Also: `stop-check.py:8-9` "the router ... blocks a Stop only for a missing must-use skill (strength stop)"; the router blocks Stop for pr-url and the verify walls, and has no stop rule. `agents-md/90-toolbox-and-vendor-rules.md`: "omc (servers; on everywhere on macOS)" is rendered on dev-mac Ubuntu boxes. `README.md:549` lists 10 commands; `ai/bin` has 19.)

Behaviour that no doc explains (README, GUIDE and the hooks README searched):

1. The macOS `caffeinate -s -w $PPID` SessionStart hook in `hooks.json` (0 hits in README and GUIDE; 3 in SPEC).
2. docs-lookup is skipped when the prompt names a symbol of this repo (`router.py:242-243`, "Fable readiness: a false docs nudge"); 0 hits.
3. abs_rewrite turns `git push` and `gh` into absolute root-owned program paths from `sandbox.excludedCommands` (`router.py:386-429`); "excludedCommands" has 0 hits.
4. `run_notify` falls back to `~/.dotfiles/bin/claude-notify` (`router.py:1765-1767`), and `base.sh:138-148` links that path into the base branch.
5. `AI_DOCTOR_MODE=no-hermes|hermes-only` (`ai-doctor:68-75`); 0 hits in docs.
6. The Codex deny text names `sudo ai-gate-skip` on every machine (`router.py:636-637`), though dev-mac has no such command.
7. On dev-mac, `stop-check.py` still starts a Python process on every SessionStart and Stop, only to return at `active_root` (`stop-check.py:226-227`).
8. Each dev-mac install runs migration undo steps: `scanners_drop` (`tools.sh:729`), `agents_drop_user` (`tools.sh:1033`), `tools_drop_user` (`tools.sh:1055`), the last30days uninstall (`claude.sh:583-606`), the `AI_DROP_*` lists (`pins.env`). README presents these as past decisions, not as steps that run each time (GUIDE not read in full).
9. `graph_symbols` reads `graphify-out/graph.json` on each later broad search and skips graphs over 50 MB (`router.py:275,297-302`).
10. `ai-start:1560-1570` writes `no-stop-check` into `.ai/enabled` when check-fast fails at adopt time, on dev-mac too, where the stop check is off anyway.

## 7. Not checked

- No test, installer or hook was run. Reachability comes from reading code and grep, not from a run on a dev-mac machine.
- The cut figures of KEEP-SIMPLIFY units are estimates from function spans, not a trial deletion.
- The server-only test lines are a keyword heuristic over test function bodies plus their names; the bodies were not read in full.
- `ai-start` (1799 lines), `aiconf.py` (2030), `ai-doctor` (1697), `ai-libs` (792), `ai-eval` (868) and `resolve.py` (768) were read in parts only.
- `docs/GUIDE.md`, `ai/SPEC.md`, `docs/TOOLS.md` were searched, not read in full; the DOC-STALE lists are samples, not a complete list.
- The `.agents/skills/verify-ai-setup` tool, `ai/evals` content and `docs/tickets` were not audited for correctness.
- Whether the 3 machines still carry server-era state (scanners, opencode, last30days, Grounded Docs) that the migration steps clean. Removing those steps before the state is gone could leave old copies.
- Codex hook features and whether Codex reaches the winner gate (its PreToolUse matcher is `Bash|apply_patch`).
- Whether any test reads the vendor rule copies in `ai/rules/vendor/`.
- `ownertext.py` block parsing was not compared line by line with `aiconf.py`.

