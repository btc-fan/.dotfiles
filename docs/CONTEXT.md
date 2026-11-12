# Context: what is installed and why

One page that lists every part. Tables only. The reasons are in `ai/SPEC.md`. The rules for each tool are in `ai/rules/<tool>.md`.
For the explanation of each tool, how tools overlap and interact: [TOOLS.md](TOOLS.md). For how the root rules reach each agent: [AGENTS-MD.md](AGENTS-MD.md).

## Rules

| Item | File | Notes |
|---|---|---|
| Root rules | `~/.config/ai/AGENTS.md` (built on each machine from `ai/agents-md/*.md` and the L0 table; the built file is not committed) | under 30 KB. Part 00 is the owner text |
| Usage contracts | `ai/rules/<tool>.md` | Vendor rules, When, Enforcement, Proof, Setup |
| Vendor text copies | `ai/rules/vendor/` | byte copies of the pinned vendor templates (one U+2014 character replaced) |
| Toolbox | `ai/TOOLBOX.md` | not loaded in sessions. One pointer line in the root rules |
| Project rules | `<project>/AGENTS.md` + a one-line `CLAUDE.md` with `@AGENTS.md` | add rules. May override style or tooling only |
| Opt-in tool blocks | `<!-- AI:<tool> v<N> START --> ... END -->` in the project AGENTS.md | skipped when the project already has text for the tool |
| Memory conventions | `ai/serena/memory_maintenance.md` -> `~/.serena/memories/global/memory_maintenance.md` | Serena template + our size caps and no-secrets rule. Read-only for agents |

## Project knowledge (per repo, made by ai-adopt)

| Item | File | Committed | Read with | Fresh when |
|---|---|---|---|---|
| Code facts | `.serena/memories/` (core, tech_stack, suggested_commands, conventions, task_completion) | yes | Serena `initial_instructions`, then `read_memory core` | fewer than 20 code commits and 5 added/deleted/renamed code files since the last memory commit |
| Serena project | `.serena/project.yml` (`initial_prompt` points at core), `.serena/.gitignore` | yes | Serena | - |
| Code graph | `graphify-out/graph.json` | no (gitignored) | `graphify query` | newer than the last code commit |
| Library docs map | `.ai/libs.md` | yes | the agent; docs rows show cached IDs | `lock:` hashes equal the lockfiles |
| Ignored | `.serena/cache/`, `.serena/project.local.yml`, `.serena/logs/`, `graphify-out/` | in `.gitignore` | - | - |
Worked example: `README.md`, section 3, example D.

## Agents

| Agent | Status | Contract |
|---|---|---|
| Claude Code + oh-my-claudecode 5.8.4 (Claude plugin, exa off) | main | `omc.md` |
| Codex + oh-my-codex 0.22.6 | main (OMX not before 2026-11-17) | `omx.md` |
| Hermes | configured, runs as user `hermes` | `hermes.md` |
| herdr 0.9.5 | configured | `herdr.md` |
| opencode 1.19.5 | always installed | `opencode.md` |
| oh-my-openagent (omo) | optional, only when asked | `omo.md` |
| Gemini CLI, Kimi CLI | later | none yet |

## MCP servers

| Server | Scope | Contract |
|---|---|---|
| Serena 2.1.0 | global | `serena.md` |
| context7 4.6.0 | global | `context7.md` |
| Grounded Docs | global, runs on the home server | `grounded-docs.md` |
| GitHub MCP | global, full access | `github-mcp.md` |
| Playwright MCP | per project only | `playwright.md` |

## Plugins and skills

| Item | Scope | Pin | Contract |
|---|---|---|---|
| ai-core (our plugin) | global | repo | this repo |
| Ponytail | global | 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846 | `ponytail.md` |
| i-have-adhd | global | 1ecea1993b7fce257ffbd686c070948b5e07eda6 | `i-have-adhd.md` |
| graphify 0.9.105 | global | PyPI | `graphify.md` |
| RTK v1.2.0 | global | tag | `rtk.md` |
| claude-seo v2.5.0 | per project (`ai-adopt --tools seo`) | 219ff485bb016314bb4c15bfc7978df61c668a4f | `claude-seo.md` |
| claude-blog v2.3.2 | per project (`ai-adopt --tools blog`) | 4f9c2cb8fd17f594e868d6c2ce0e8fb2c971f987 | `claude-blog.md` |
| mattpocock skills (5 global) | global | 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d | `mattpocock-skills.md` |
| prompting-claude-and-codex | global | dated snapshot | `prompting-claude-and-codex.md` |
| ui-ux-pro-max v2.15.0 | per project | a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5 | `ui-ux-pro-max.md` |
| llm-wiki-compiler 1.5.0 | per project | c9c8734be8a0b854c1547cfa3ee97f0b8c6bfa5f | `llm-wiki-compiler.md` |

Dropped: caveman (overlaps i-have-adhd), the context7 plugin (duplicate of the MCP). Not adopted: superpowers, Docker Dynamic MCP, Smithery, MetaMCP, Nix tools, sfw, context7 On-Premise, an LLM classifier router.
Every pin lives in `ai/pins.env`. The table above must match it.

## Hooks (global, inside plugin ai-core)

| Event | What | Layer |
|---|---|---|
| SessionStart | rules with `when: session_start` (status lines); the L0 table after compaction or /clear (startup and resume get only the status lines; the table is in the root rules) | L1 |
| UserPromptSubmit | regex rules, then forced-eval text when a rule matched | L2, L3 |
| PreToolUse | gates (audit, secret scan, PR rules), nudges (serena-first, graph-first) | L4, L3 |
| PostToolUse | graph-update, docs-on-dependency, agent-docs, no-em-dash lint, skill proof | L3, L7 |
| Stop | miss log, then `claude-notify` | L7 |
| Notification | `claude-notify` | owner hook |
| SessionStart (startup, resume) | caffeinate | owner hook |
| Vendor hooks | Serena activate and cleanup, graphify guard, RTK rewrite, Ponytail, i-have-adhd, herdr status | per tool |

Owner hooks come from the owner's hooks.json. Each hook finishes well under the 30 s limit. The L2 hook has a 10 s timeout and falls back to L3.

## Routing

Source: `ai/routing.yaml` (version 3). 31 rules (24 global, 7 opt-in, 4 are gates), a tie-break table, and a `layers` block.
Rules by group:
- Start of work: `kickoff`, `no-ai-base`.
- Project knowledge: `project-knowledge` (session start status line), `no-memories`, `knowledge-check` (after a commit).
- Code navigation: `no-graph`, `graph-first`, `serena-first`, `graph-update`.
- Safety: `audit-before-install`, `secret-scan`, `no-sudo`, `no-em-dash`.
- PR: `pr-rules`.
- Topics: `seo-not-enabled`, `blog-not-enabled` (suggest `ai-adopt --tools seo|blog`), `docs-lookup`, `browser-not-enabled`, `docs-on-dependency`, `github`, `prompting-others`, `agent-docs`, `wait-what`, `toolbox`.
- Opt-in: `seo`, `blog`, `ui`, `tracker-flow`, `domain-docs`, `browser`, `knowledge-wiki`.
Tie-break examples: one post file means blog-*, a URL means seo-*. "grill me" means grilling, "deep interview" means OMC deep-interview. Code symbols mean Serena. Library docs mean `.ai/libs.md` IDs, then Grounded Docs, then context7.
Action placeholders the router fills at fire time: `{knowledge_index}`, `{knowledge_delta}`, `{libs_hits}`, `{origin_slug}`. `docs-lookup` also fires when the prompt names a library from `.ai/libs.md` (`prompt_libs`).
To read the full table: `ai/routing.yaml`. Do not copy it here.

## Commands

| Command | What |
|---|---|
| `ai-doctor` | checks the whole setup |
| `ai-render` | builds routing.json, L0 table and the root file |
| `ai-sync` | after a pull: runs `ai-render`, refreshes the copied rule blocks (Codex, Hermes). `--check` compares, `--install-hook` makes `git pull` run it |
| `agent-audit npm\|pypi\|dir\|skill <target>` | audit before install |
| `ai-start` | new project: grilling, propose tools, write project config |
| `ai-adopt` | existing repo: add the project layer and the knowledge layer (Serena project + onboarding, graph, `.ai/libs.md`, gitignore lines) |
| `ai-libs` | `.ai/libs.md`: `--sync` writes it from the lockfiles, `--check` exits 1 when stale. Offline-safe. Sends only public library names to context7, one call per library once; local and private-registry packages never |
| `claude-notify` | notifications |
| `pr-resume` | reads the author-sessions block of a PR |

## State and logs

| File | Written by |
|---|---|
| `~/.local/state/ai/audit.log` | agent-audit: `<iso-time> <ecosystem> <name> <version> PASS\|FAIL` |
| `~/.local/state/ai/gates.log` | gates and escape hatches |
| `~/.local/state/ai/misses.jsonl` | Stop hook: a rule fired and no matching tool call followed |
| `~/.local/state/ai/fired.jsonl` | skill proof: model calls (`Skill` matcher) and typed commands (UserPromptExpansion) |
| `~/.local/state/ai/docs-ids.jsonl` | router: library and docs ID of each docs MCP call (context7, Grounded Docs). `ai-libs` reads it as a cache |
| `~/.local/state/ai/nudges.json` | quiet windows and once-per-library state |
| `~/.local/state/ai/router-errors.log` | internal router errors (the router fails open) |
| `~/.local/state/ai/managed-keys.json` | what install added (for uninstall) |
| `~/.cache/graphify-queries.log` | graphify |
| `rtk gain --history` | RTK |

## Evals

`ai/evals/`: `tools.md`, `claude-seo.md`, `claude-blog.md`, `ui-ux-pro-max.md`, `mattpocock-and-llmwiki.md`, `HOWTO.md`.

## Known gaps

- opencode has no hooks, no gates and no miss log. Only the root rules apply there.
- Hermes has no per-prompt matching of skills. A small plugin does L2 and L3.
- Skills that only the owner can type (grill-me, wait-what, retro, i-have-adhd) cannot be forced. The agent suggests them. Kickoff uses the model-invoked `grilling`, or OMC deep-interview when grilling is not installed.
- opencode and Hermes get the knowledge flow only from the root rules (no session start line, no commit nudge).
- Several vendor facts are marked UNVERIFIED in the contracts. They need a test on the server.
