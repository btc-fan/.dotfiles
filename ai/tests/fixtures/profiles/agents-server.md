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


Output shape
Follow i-have-adhd in every reply. It is always on.
Its list "When to break the rules" applies.
Turn it off for one session only when I say "stop adhd mode".
The 60-word limit has two exceptions: the state line and the one next action.
Documents, PR bodies and code comments do not use this shape. They follow the writing style above.

RTK
A hook rewrites shell commands to rtk (example: git status becomes rtk git status) to cut output.
- Full output (security tools, debugging): rtk bypass <cmd>.
- A refused command: rtk pipeline explain shows the rule. Never use --ultra-compact (removed in 1.0).
- uv run is not rewritten: write uv run rtk pytest and uv run rtk ruff check by hand.


Code navigation
- Order in a repo: the Map and Libraries sections of its AGENTS.md, then graphify query (structure), then Serena symbol tools (definitions, references, edits), then a narrow rg and reading only the located lines. Do not scan whole folders.
- Serena and graphify are on in every project unless .ai/enabled says no-serena or no-graph (the session start line says so). Serena keeps no memories: the Map is the one knowledge place.
- After a commit that adds, deletes or renames modules, update the Map section. After a dependency change, run ai-libs --sync. Never put secrets or personal data in AGENTS.md.
- Library, SDK, API or CLI code: look up docs before you write it. Use context7 query-docs with the ID from the Libraries section (resolve-library-id only when there is no ID). If context7 has nothing: the official docs site, then the library source, and say so. No general web search for docs (Codex too). No secrets or private code in a docs query.
- GitHub: the gh CLI, read-only (view, list, diff, checks) unless I ask for a change. A PR follows the pull request rules below.


Audit and gates
- Before you install a package, MCP server, skill or plugin: agent-audit npm|pypi|dir|skill <target> (also pypi httpx==0.28.1). Exit 3 = a scanner could not run: no PASS, not a finding. A finding means stop and show it to me. Exact versions only, no @latest, no curl piped to a shell.
- A skill or plugin with a skill-scanner HIGH or CRITICAL finding is never installed (agent-audit exit 4), not even for an accepted version. Only the owner can skip the scan (install.sh --skip-scan <tool>); never add that flag yourself.
- Never git add -A or git add . blindly: git status first, then add your changed files by name. Sandbox placeholder files in project roots are ignored globally; a real new .mcp.json or .claude/commands needs git add -f.
- Never commit a key, token or password. The secret-scan gate blocks commit and push on a hit.
- Never edit .env files or print their values. New settings go into the example file (.env.example) and the config code.
- Never deploy to production or touch a production host without my explicit OK for that deploy.
- A failing test is a blocker, never "pre-existing" or "expected": no skip, no delete, no failure allowlist. Fix the code; change a test only when you are sure the test is wrong, and say why.
- Commands run in a sandbox. A network or permission error is final too: do not try to get around it (no other path, no SSH instead of HTTPS); tell me the command and the error.
- A blocked gate is final for you. Only I can let it through (sudo ai-gate-skip). Never try to get around it; tell me the command and why.


No root
Never run sudo or try to get root (su, pkexec, setuid tricks, editing sudoers). When something needs root (apt, systemctl, files in /etc), stop and give me the exact command to run.
Box work on a server: the box tool (MCP server box: list, new, exec, logs, status, restart, ports, url, snapshot, doctor, help); outside a sandbox also plain proj-agent <subcommand>; never sudo (the no-sudo gate blocks sudo proj-agent like every other sudo).


Pull requests
The PR body follows the `pr` skill (Matt Pocock). Use this template:
```markdown
## Summary
<smallest visual that shows the change; a ```mermaid diagram is required, other visuals are optional>
## Evidence
- **Before:** <failing test run, output or screenshot>
  **After:** <passing run, output or screenshot>
## Merge Danger
**Door:** <one-way or two-way> <reason>
**Blast Radius:** <what can break>
```
Summary must hold a Mermaid diagram of the change.
Evidence is the check-fast command and the tail of its output as After. Add Before when a test went red first. A project with a verify-<app> skill also names the skill run, its evidence path and the e2e test.
Door must say one-way or two-way. Blast Radius must say what can break.
Also required: Docs (files, or "none, because ..."), Changed guards (each edited or removed test and why, or "none"), and on a fix PR Ledger: R-NNN. A fix PR has a test file in its diff.
The author-sessions block goes at the end (next section). The pr-rules gate blocks a PR without these parts (placeholder text counts as missing).

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


Characters
Never write the em dash character (U+2014). Not in code, docs, commit messages, PR text or replies.
Use "-", ":" or a new sentence. A hook lints every file you write.


Prompting other agents
Goal and what is ruled out, absolute file paths, one narrow task, expected output and format, read-only unless I said otherwise. No --bare on claude -p. Check the result yourself. Skill: prompting-claude-and-codex.


Other agents
claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>"; opencode run "<task>" --format json. Hermes never hands work to Claude. Details: ~/.config/ai/rules/<tool>.md.


## Routing table (L0)
Generated from ai/routing.yaml v4 by ai-render. Do not edit here.
nudge = do it unless it clearly does not apply. gate = the step is blocked until the condition is met.
opt-in = only in projects that enabled the tool (ai-start, ai-adopt).

| Rule | When | Do |
|---|---|---|
| project-knowledge (nudge) | session start in a code repo | Read the Map and Libraries sections of this repo's AGENTS.md first, then search narrowly. (status line: memories, graph, docs map) |
| no-ai-base (nudge) | session start: repo without .ai/base-version | No AI base or Map here. Suggest the owner runs ai-adopt. |
| knowledge-check (nudge) | after a git commit | Update mem:core, run ai-libs --sync or graphify update, as the commit needs. |
| audit-before-install (gate) | before a package install command | agent-audit this package first. No @latest, no curl-to-shell. |
| secret-scan (gate) | before git commit or push | Secret scan found a key, token or password. Remove it before commit or push. |
| no-sudo (gate) | any sudo, su, doas, pkexec | No sudo for agents: give the owner the exact command. Box work on a server: the box tool (MCP server box); outside a sandbox also plain proj-agent <subcommand>; never sudo. |
| no-destroy (gate) | rm -r of data, home or repo root; force push or delete of main; reset --hard with changes; clean -x at the root; compose down -v; DROP/TRUNCATE on a protected DB | Destructive command: give the owner the exact command and the reason. Rebuildable folders (node_modules, .venv, dist, build) are fine. |
| pr-rules (gate) | before gh pr create or edit | PR body (pr skill template): Summary with a Mermaid diagram, Evidence (Before and After), Merge Danger (Door: one-way or two-way; Blast Radius), Docs, Changed guards (Ledger on fix PRs), author-sessions block at the end. |
| ledger-nudge (nudge) | before an edit in a regression-ledger area (tier long) | Edit in a docs/REGRESSIONS.md area (long tier): keep its R-IDs green, run their tests. |
| no-em-dash (nudge) | after a write with U+2014 | Remove the em dash (U+2014). Use '-', ':' or a new sentence. |
| docs-lookup (nudge) | docs, SDK or library prompt | Library code: context7 query-docs with the ID from the Libraries section (resolve only if missing), then the official docs site. (cached IDs) |
| feature-grill (nudge) | feature request prompt (add, implement, build ... a feature, endpoint, page; RO, RU) | grill-with-docs (where the project links it; else grilling), for 3+ files to-spec then to-tickets, then per slice: check-fast, verify-<app> evidence, e2e. Trivial: none needed. |
| verify-before-done (nudge) | after a code edit in a project with a verify-<app> skill (tier mvp, long) | Before done: check-fast, then verify-<app> on the changed feature (evidence), then e2e tests. |
| seo-not-enabled (nudge) | SEO prompt, project without claude-seo | claude-seo is off in this project. Suggest: ai-adopt --tools seo. Do not enable it yourself. |
| blog-not-enabled (nudge) | blog prompt, project without claude-blog | claude-blog is off in this project. Suggest: ai-adopt --tools blog. Do not enable it yourself. |
| browser-not-enabled (nudge) | browser prompt, project without Playwright MCP | No Playwright MCP in this project. Suggest: ai-adopt --tools browser. Do not install a browser tool yourself. |
| serena (nudge, opt-in) | session start, Serena on (default) | Serena is on here (no memories, the Map is the knowledge place): get_symbols_overview / find_symbol for definitions, find_referencing_symbols for users, replace_symbol_body for edits. |
| graph (nudge, opt-in) | session start, graphify on (default) | graphify is on here: graphify query for structure before rg; the graph refreshes itself after commits, merges and checkouts. |
| omc (nudge, opt-in) | session start, oh-my-claudecode on here | oh-my-claudecode is on here: its skills and agents are available (/oh-my-claudecode:...). It writes .omc/ in this repo (keep it out of commits except .omc/skills/). |
| seo (nudge, opt-in) | SEO prompt | SEO task: claude-seo first (/seo audit <url>, /seo page <url>). Other agents: hand off to Claude only when it is logged in, else follow the skill files. |
| blog (nudge, opt-in) | blog prompt | Blog task: claude-blog first (claude-blog:blog routes). Post file: blog-*. Site: seo-*. Other agents: hand off to Claude only when it is logged in, else follow the skill files. |
| browser (nudge, opt-in) | browser prompt (screenshot, click, e2e) | Browser work: Playwright MCP (headless, isolated on servers). |
| ui (nudge, opt-in) | UI prompt or UI file | UI work: use ui-ux-pro-max. Ask before paid image generation or any npx ...@latest. |
| tracker-flow (nudge, opt-in) | tickets, spec, triage, backlog prompt | to-spec, then to-tickets (on when the project's skills line lists them). Tickets go to docs/tickets/<feature>/ (docs/agents/issue-tracker.md); never GitHub issues or labels without the owner. |
| domain-docs (nudge, opt-in) | glossary, domain model, ADR prompt | Use grill-with-docs / domain-modeling (GLOSSARY.md, docs/adr/). |
| knowledge-wiki (nudge, opt-in) | wiki or knowledge base prompt | Use llm-wiki-compiler (costs LLM tokens per compile). |

Tie-breaks (use the first, not the second):
- one post file, or a post to be written: claude-blog:blog-*, not claude-seo:seo-*
- URL, domain, whole site: claude-seo:seo-*, not claude-blog:blog-*
- new app or project (kickoff): grilling (grill-with-docs where the project links it; typed: /grill-me), not OMC deep-interview (fallback)
- deep interview, ambiguity score: OMC deep-interview, not matt grilling
- library API docs: context7 with the Libraries ID, not web search


Tools
- Unsure which tools, skills or options exist on this machine: run ai-info first (and server-info on a server).
- Opt-in per project (ai-adopt --tools <id>): seo, blog (claude-seo, claude-blog), browser (Playwright MCP), omc (servers; on everywhere on macOS), ui and others. Off in a project: suggest the command, never install it yourself. Hermes follows the claude-seo and claude-blog skill files itself; Codex and opencode too, unless Claude is logged in (Codex also needs my OK for a network run).
- OMC (on servers only where a project turned it on: ai-adopt --tools omc): plan, execute, review, verify. This file and the gates win over OMC defaults. Ponytail: smallest correct diff, never cut validation or security.
- last30days (Claude, on everywhere): what people say about a topic in the last 30 days (Reddit, X, HN, YouTube, Polymarket, web): /last30days <topic>. It sends the topic out; ask before its setup wizard or any key.
- Ready tools that are not installed: ~/.config/ai/TOOLBOX.md (audit before the first install).

<!-- generated by ai/bin/ai-render from ai/agents-md/ and ai/routing.yaml; edit those -->
