# Context: what is installed and why

One page that lists every part. Tables only. The reasons are in `ai/SPEC.md`. The rules for each tool are in `ai/rules/<tool>.md`.
For the explanation of each tool, how tools overlap and interact: [TOOLS.md](TOOLS.md). Security model (sandbox, boxes, planted config): [SECURITY.md](SECURITY.md). For how the root rules reach each agent: [AGENTS-MD.md](AGENTS-MD.md).

## Rules

| Item | File | Notes |
|---|---|---|
| Root rules | `~/.config/ai/AGENTS.md` (built on each machine from `ai/agents-md/*.md` and the L0 table; the built file is not committed) | under 30 KB. Part 00 is the owner text |
| Usage contracts | `ai/rules/<tool>.md` | Vendor rules, When, Enforcement, Proof, Setup |
| Vendor text copies | `ai/rules/vendor/` | byte copies of the pinned vendor templates (one U+2014 character replaced) |
| Toolbox | `ai/TOOLBOX.md` | not loaded in sessions. One pointer line in the root rules |
| Project rules | `<project>/AGENTS.md` + a one-line `CLAUDE.md` with `@AGENTS.md` | add rules. May override style or tooling only |
| Opt-in tool blocks | `<!-- AI:<tool> v<N> START --> ... END -->` in the project AGENTS.md | skipped when the project already has text for the tool |

## Project knowledge (per repo, in its AGENTS.md, made by ai-adopt)

| Item | Where | Committed | Fresh when |
|---|---|---|---|
| Map | `<!-- AI:map START -->` ... `<!-- AI:map END -->` in AGENTS.md: entry points, where things live, run and test, conventions; <= 60 lines | yes | `knowledge-check` asks for an update after a commit that adds, deletes or renames modules |
| Libraries | `<!-- AI:libraries START lock: ... -->` ... `<!-- AI:libraries END -->` in AGENTS.md: lib, version, context7 ID, note | yes | the START line hashes equal the lockfiles (`ai-libs --check`) |
| Playwright (opt-in) | `enabledPlugins` `ai-playwright@ai` in the project `.claude/settings.json`, `.codex/config.toml` | yes | - |
| Serena (default on; `no-serena` opts out) | `.serena/project.yml`; `.serena/cache/` gitignored | yes, except the cache | Serena updates its index itself |
| Code graph (default on; `no-graph` opts out) | `graphify-out/graph.json`, gitignored; `graphify hook install` rebuilds it after commit, checkout, merge, rebase (after agent git calls, which run no hooks on a server, the router starts `graphify update` in the background) | no | newer than the last code commit |
Worked example: `README.md`, section 3, example D.

## Agents

| Agent | Status | Contract |
|---|---|---|
| Claude Code | main | `omc.md` (OMC) |
| oh-my-claudecode 5.8.4 (Claude plugin, exa off) | macOS: on; servers: per project (`ai-adopt --tools omc`) | `omc.md` |
| Codex + oh-my-codex 0.22.6 | main (OMX not before 2026-11-17) | `omx.md` |
| Hermes | configured, runs as user `hermes` | `hermes.md` |
| herdr 0.9.5 | installed by default (macOS where present) | `herdr.md` |
| opencode 1.19.5 | macOS; servers only with `AI_EXTRA_AGENTS=opencode` | `opencode.md` |
| oh-my-openagent (omo) | optional, only when asked | `omo.md` |
| Gemini CLI, Kimi CLI | later | none yet |

## MCP servers

| Server | Scope | Contract |
|---|---|---|
| Serena 2.1.0 | global (Claude plugin ai-serena on at user scope, Codex, Hermes); `no-serena` opts a project out; mode no-memories | `serena.md` |
| context7 4.6.0 | global | `context7.md` |
| box (ours, ai-core) | global; does something only on a server with `proj-agent` | `box.md` |
| Playwright MCP | per project only | `playwright.md` |

## Plugins and skills

| Item | Scope | Pin | Contract |
|---|---|---|---|
| ai-core (our plugin) | global | repo | this repo |
| Ponytail | global | 96608e078b2d5ea607c5c3b8b5a54d1c1fba6846 | `ponytail.md` |
| i-have-adhd | global | 1ecea1993b7fce257ffbd686c070948b5e07eda6 | `i-have-adhd.md` |
| graphify 0.9.105 | global CLI, on in every project (`no-graph` opts out) | PyPI | `graphify.md` |
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
| PreToolUse | gates (audit, secret scan, no sudo, PR rules) | L4 |
| PostToolUse | knowledge-check after a commit, no-em-dash lint, docs ID log, skill proof | L3, L7 |
| Stop | miss log, then `claude-notify` | L7 |
| Notification | `claude-notify` | owner hook |
| SessionStart (startup, resume) | caffeinate | owner hook |
| Vendor hooks | RTK rewrite, Ponytail, i-have-adhd, OMC, herdr status | per tool |

Owner hooks come from the owner's hooks.json. Each hook finishes well under the 30 s limit. The L2 hook has a 10 s timeout and falls back to L3.

## Routing

Source: `ai/routing.yaml` (version 4, owner decision 2026-11-12: passive context beats nudges). 22 rules (12 global, 10 opt-in, 4 are gates), a tie-break table of 5 rows, and a `layers` block.
Rules by group:
- Session start: `project-knowledge` (status line: Map, Libraries, opt-in tools), `no-ai-base`.
- After a commit: `knowledge-check` (update the Map, `ai-libs --sync`; silent when nothing applies). The graph refreshes itself: after agent git calls the router starts `graphify update` in the background.
- Gates: `audit-before-install`, `secret-scan`, `no-sudo`, `pr-rules`.
- Lint and docs: `no-em-dash`, `docs-lookup` (also fires on a library name from the Libraries section).
- Off in this project, suggest it: `seo-not-enabled`, `blog-not-enabled`, `browser-not-enabled`.
- Default on (opt out with `no-serena`, `no-graph`): `serena`, `graph`. Opt-in catalog (`ai-adopt --tools <id>`): `omc`, `seo`, `blog`, `browser`, `ui`, `tracker-flow`, `domain-docs`, `knowledge-wiki`.
- Removed in v4 (ignored in the logs or unmeasured): `kickoff`, `no-memories`, `no-graph`, `graph-first`, `serena-first`, `graph-update`, `docs-on-dependency`, `github`, `prompting-others`, `agent-docs`, `wait-what`, `toolbox`.
Tie-breaks: post file means blog-*, a URL means seo-*; new app means grilling; "deep interview" means OMC deep-interview; library docs mean context7 with the Libraries ID, not web search.
Action placeholders the router fills at fire time: `{knowledge_index}`, `{knowledge_delta}`, `{libs_hits}`, `{claude_handoff}`.
To read the full table: `ai/routing.yaml`. Do not copy it here.

## Commands

| Command | What |
|---|---|
| `ai-info` | what this machine offers (agents, plugins, skills, MCP, gates, opt-in tools, current repo state); `--short` for the login screen. Local, no network, no secrets |
| `ai-doctor` | checks the whole setup |
| `ai-render` | builds routing.json, L0 table and the root file |
| `ai-sync` | after a pull: runs `ai-render`, refreshes this user's copied rule blocks (Codex; Hermes and `/etc` only through the admin `install.sh --update`). `--check` compares, `--install-hook` makes `git pull` run it |
| `agent-audit npm\|pypi\|dir\|skill <target>` | audit before install |
| `ai-start` | new project: grilling, propose tools, write project config |
| `ai-adopt` | existing repo: project layer, the Map and Libraries sections of AGENTS.md, opt-in tools (`--tools omc,seo,blog,browser,...`), Serena index and graph build with git hooks |
| `ai-libs` | the Libraries section of AGENTS.md: `--sync` writes it from the lockfiles, `--check` exits 1 when stale. Offline-safe. Sends only public library names to context7, one call per library once; local and private-registry packages never |
| `claude-notify` | notifications |
| `pr-resume` | reads the author-sessions block of a PR |

## State and logs

| File | Written by |
|---|---|
| `~/.local/state/ai/audit.log` | agent-audit: `<iso-time> <ecosystem> <name> <version> PASS\|FAIL` |
| `~/.local/state/ai/gates.log` | gate blocks and owner skips (`sudo ai-gate-skip`; window in root-owned `/etc/ai/gate-skip`) |
| `~/.local/state/ai/misses.jsonl` | Stop hook: a rule fired and no matching tool call followed |
| `~/.local/state/ai/fired.jsonl` | skill proof: model calls (`Skill` matcher) and typed commands (UserPromptExpansion) |
| `~/.local/state/ai/docs-ids.jsonl` | router: library and context7 ID of each docs call. `ai-libs` reads it as a cache |
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
- Skills that only the owner can type (grill-me, wait-what, retro, i-have-adhd) cannot be forced. The agent suggests them. For a new app the tie-break names the model-invoked `grilling`.
- opencode and Hermes get the knowledge flow only from the root rules (no session start line, no commit nudge).
- Several vendor facts are marked UNVERIFIED in the contracts. They need a test on the server.
