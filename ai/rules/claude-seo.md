# claude-seo

Pin: v2.5.0 = 219ff485bb016314bb4c15bfc7978df61c668a4f. Installed on every machine, enabled per project only. Source: https://github.com/AgriciDaniel/claude-seo/blob/219ff485bb016314bb4c15bfc7978df61c668a4f/

## Vendor rules (verbatim)
No user-facing CLAUDE.md or AGENTS.md block exists. Closest routing text:
- Hub description tail (`skills/seo/SKILL.md:3`): "Use this hub only when the SEO domain is clear and the requested workflow is not; otherwise use the specific seo-* skill."
- Orchestration Logic: "For individual commands, load the relevant sub-skill directly."
- seo-audit: "Use only for site-wide checks; use seo-page for one URL or seo-technical for a technical-only review." seo-page: "Use only for a single-page review." seo-schema: "Use only when structured data or rich-result markup is requested."

## When / when not
- Input is a URL, a domain, or "why does my site not rank": seo-*. Whole site: seo-audit (up to 15 agents, confirm first). One URL: seo-page. Narrow topic: the matching seo-* skill.
- One post file on disk, or writing, rewriting or translating a post: claude-blog, never seo-*.
- Not SEO: code or security "audit", dependency audit, database "schema", chart "flow", "map" functions.
- Ask the owner first: `indexnow_submit`, `indexing_notify`, image generation, DataForSEO, any Google sign-in.
- Opt-in per project (owner decision 2026-11-12: off by default, saves about 12k tokens per session with claude-blog). Turn it on for one project: `ai-adopt --tools seo` (or `ai-start --tools seo`). It adds `seo` to `.ai/enabled` and sets `"enabledPlugins": {"claude-seo@agricidaniel-claude-seo": true}` in the project `.claude/settings.json` (either one alone also counts as on). Off again: remove both. Install writes `enabledPlugins` false at user scope; project and local settings win over user.
- The opt-in is for Claude only (plugin skill listing costs tokens). Codex, opencode and Hermes read the skill files on demand, which costs no listing tokens, so for them the pack counts as on everywhere.
- Claude in a project without it: the router row `seo-not-enabled` says so in one line. Suggest the command to the owner. Do not install or enable it yourself.
- Hermes: never hand off to Claude. Follow the skill files directly.
- Codex: hand off (`claude -p "<task with absolute path>" --output-format stream-json --verbose`, no `--bare`) only when `claude` is usable: logged in for that user and network allowed (the default Codex sandbox has none; the owner must approve an escalated run). Else follow the skill files directly.
- opencode: hand off as above when `claude` is logged in for that user (or `omc ask claude`), else follow the skill files. On a hand-off, ask for the result file path and the Skill names back.
- Skill files: audited copies, readable by every user: `/opt/agent-plugins/claude-seo` and `/opt/agent-plugins/claude-blog` on Linux, `~/.local/share/ai/plugins/` on macOS. Open `skills/seo/SKILL.md`, then the sub-skill it names. The router row says which case applies (placeholder `{claude_handoff}`).

## Enforcement
- L0 (mandatory: plugin skill descriptions get cut when the listing is over budget). Rows, with RO and RU triggers:
  `site/URL SEO audit | audit SEO, analiza site, аудит сайта | claude-seo:seo-audit`
  `one URL | pagina asta, эта страница | seo-page`
  `indexing, robots, speed, CWV | indexare, viteza, индексация, скорость | seo-technical`
  `JSON-LD of a page | date structurate, микроразметка | seo-schema (post file: blog-schema)`
  `AI citation, GEO | citari AI, цитирование ИИ | seo-geo (post file: blog-geo)`
  `plan/strategy | plan SEO, SEO-стратегия | seo-plan`; `sitemap | sitemap, карта сайта | seo-sitemap`; `hreflang | hreflang, мультиязычность | seo-hreflang`; `backlinks | backlink-uri, обратные ссылки | seo-backlinks`
- L1: the routing table comes back after compaction or /clear (startup and resume rely on the root rules). Table only.
- L2: gated by a regex (URL, seo, serp, backlink, sitemap, hreflang, schema, llms.txt, core web vitals, RO and RU words). Keep the "none" option.
- L3: `/seo `, `seo-` command names, a bare URL with audit, check, analiza, проверь.
- L4: not a skill gate (false blocks). A permission gate for `indexnow_submit|indexing_notify|dataforseo|google_auth.py --auth|generate.py`: ask. Block `pip install` and unpinned `npx lighthouse`.
- L5: plugin agents cannot be edited and cannot carry hooks. Own subagents get the table through SubagentStart.
- L6: descriptions are English only. RO and RU triggers live in L0, L2, L3.
- Plugin skills cannot be hidden one by one (`skillOverrides` ignores them). That is why the plugin is off at user scope and on per project: about 12k tokens per session with claude-blog.

## Proof
Eval cases: `ai/evals/claude-seo.md` (3 should-fire including RO and RU, 2 should-not-fire per skill). Pass bar: 3 of 3 fire, 0 of 2 false fire. Re-run on every model or pin change.
- Signal 1: Skill tool_use `claude-seo:seo-<x>`. Signal 2: Bash `claude-seo run <script>` or a report file.
- Seo-image-gen and seo-dataforseo are extensions: a paid call without owner consent is a hard fail.

## Setup checklist
1. Prerequisites: Python 3.11 to 3.14, git, Claude Code 1.0.33 or newer, node on PATH. Ubuntu 22.04 has Python 3.10: install 3.11 or newer and set `CLAUDE_SEO_PYTHON`.
2. Install (pinned tag): `claude plugin marketplace add AgriciDaniel/claude-seo#v2.5.0`, then `claude plugin install claude-seo@agricidaniel-claude-seo` (user scope), then disable it at user scope (`enabledPlugins` false). The audited copy for other agents goes to `/opt/agent-plugins/claude-seo` (Linux) or `~/.local/share/ai/plugins/claude-seo` (macOS). Record the sha in `ai/pins.env` and compare after install. Do NOT also run its `install.sh`. Extension installers stay off.
3. Marketplace auto-update stays off (default for third-party marketplaces). Check it in `/plugin`.
4. Keys: none for the free core. Optional keys go in `~/.config/ai/secrets.env`, never through installers.
5. Per machine: `/seo setup` once (creates a venv, installs requirements, Chromium). Then `/seo doctor`. A Chromium failure is not fatal.
6. Local paths, never commit: `~/.config/claude-seo/`, `~/.cache/claude-seo/`, the data dir (`~/.local/share/claude-seo` on Linux).
7. Per project: `ai-adopt --tools seo` (`.ai/enabled` + project `.claude/settings.json` `enabledPlugins`). Gitignore report and PDF outputs after the first run shows the names.
8. Verify: `claude plugin list` shows claude-seo 2.5.0, disabled at user scope; inside an enabled project `/plugin` shows it enabled. `/seo doctor` clean. Smoke: `/seo page https://example.com` gives Skill `claude-seo:seo-page`. Compare the skill listing text with v2.5.0 (one copy seen was not v2.5.0).
9. Cleanup: `claude plugin uninstall claude-seo@agricidaniel-claude-seo`, `claude plugin marketplace remove AgriciDaniel/claude-seo`, delete the three local paths.
Collisions: the nine claude-blog pairs. The tie-break table in `ai/routing.yaml` decides: post file means blog-*, URL means seo-*.
