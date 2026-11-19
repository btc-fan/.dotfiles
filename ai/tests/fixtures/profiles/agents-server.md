Lead with the answer. Hard limit: 60 words unless I ask for detail. Tables and lists count. Code blocks do not.

Reporting style
Reports and answers to me use the writing style below, in the reply shape of the Output shape section. Keep them short with fewer facts, not with fewer words per sentence: write full sentences with their articles and verbs.

Keep facts exact. Never drop a unit, a version, a file path, or a number to save words.

Writing style
Write all text with the rules of ASD-STE100 Simplified Technical English: chat answers, reports, documents, code comments and PR bodies. STE is the controlled language that aerospace and defense manufacturers use for maintenance documentation. Its rules make sure that a tired reader who is not a native English speaker cannot misread an instruction.

Write for that tired reader. Each sentence must survive one read.

Standing permission
You have my standing permission to run every command the task needs, in every session and in every agent (Claude Code, Codex, others). Keep going until a real block stops you: a gate, a denied call, or a step only I can do (a typed /skill, a login, a merge OK). Then give me the exact command or step. The gates and the other rules in this file still apply.

Personal files
Never move, split or rewrite my personal files (shell start-up files, ~/.config, secrets files) outside the task. A "clean up" or "commit everything" request that hits one: leave it as it is and tell me.

Project rules
Write a rule that belongs to one project outside the AI blocks of its AGENTS.md (the text between the AI:<name> START and END markers): under "## Project rules" or in the project's own sections. The AI blocks belong to the dotfiles setup, and an update refreshes them.

Code organisation
Before you copy a nearby approach, check it against this file. If they contradict, ask me how to proceed.

Structure code top-down: entry points at the top, implementation details at the bottom.

Put an empty line between logical blocks. Code should read like text with paragraphs.


Output shape
Follow i-have-adhd in every reply. It is always on.
Its list "When to break the rules" applies.
Turn it off for one session only when I say "stop adhd mode".
The 60-word limit has two exceptions: the state line and the one next action.
Documents, PR bodies and code comments do not use this shape. All text, replies too, uses the writing style above.

RTK
A hook rewrites shell commands to rtk (example: git status becomes rtk git status) to cut output.
- Full output (security tools, debugging): rtk bypass <cmd>.
- A refused command: rtk pipeline explain shows the rule. Never use --ultra-compact (removed in 1.0).
- uv run is not rewritten: write uv run rtk pytest and uv run rtk ruff check by hand.


Code navigation
- Order in a repo: the Map and Libraries sections of its AGENTS.md first. Then:
  1. Wide question (where, how, what breaks): graphify query "<question>" --budget 1500, or graphify affected "<path>::<symbol>".
  2. Exact symbol, its callers, an edit: Serena find_symbol, find_referencing_symbols, replace_symbol_body.
  3. Text only (strings, config, logs): a narrow rg, then read only the located lines. Do not scan whole folders.
- Serena and graphify are on in every project unless .ai/enabled says no-serena or no-graph (the session start line says so). Serena down: say so, use graphify and rg, and tell the owner. The owner can ask you to fix or switch it off (add no-serena to .ai/enabled).
- Knowledge lives in the repo only: the Map, GLOSSARY.md, docs/adr, docs/research. No Serena memories, no Claude auto memory.
- After a commit that adds, deletes or renames modules, update the Map section. After a dependency change, run ai-libs --sync. Never put secrets or personal data in AGENTS.md.
- Library, SDK, API or CLI code: look up docs before you write it. Use context7 query-docs with the ID from the Libraries section (resolve-library-id only when there is no ID). If context7 has nothing: the official docs site, then the library source, and say so. No general web search for docs (Codex too). No secrets or private code in a docs query.
- GitHub: the gh CLI, read-only (view, list, diff, checks) unless I ask for a change. Exception: the git workflow below (push the feature branch, draft PR, gh pr ready, gh pr merge after the owner's OK). A PR follows the pull request rules below.


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
The author-sessions block goes at the end (next section). The pr-rules gate blocks a PR without the Mermaid diagram, Evidence, Door, Blast Radius or the author-sessions block, and a fix PR without a test file (placeholder text counts as missing). Docs, Changed guards and Ledger get a warning only.

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


Git workflow (from the Matt Pocock skills; owner 2026-11-15, merge and release 2026-11-16)
- Feature or fix work: before the first edit, create a branch named after the feature slug. Use the same slug as docs/specs/<slug>.md and docs/tickets/<slug>/ (a fix: fix-<slug>). Never commit on main or master. A trivial change (typo, one line) also gets its own branch.
- Commit each ticket on that branch (/implement commits at the end). Move the finished ticket file to docs/tickets/<slug>/done/ in the same commit.
- After the first ticket commit: push the branch and open a draft PR (gh pr create --draft, with the full PR body). Push each later ticket to it.
- Feature done: run the ship skill (make check, verify-<app>, code-review, security review, UI checklist, Evidence, gh pr ready). Then ask the owner.
- Every PR goes through the owner. Merge (gh pr merge --squash --delete-branch) only after the owner's latest message says merge or approve; else the owner merges. Never push to main or master. The merge-approval gate enforces both.
- After a merge (yours, or the owner's on GitHub): delete the merged branch locally and on the remote, and its worktree (git worktree remove <path>, then git worktree prune). A squash merge hides the branch from git branch --merged: check that gh pr view <branch> --json state says MERGED, then git branch -D. Ticket branches go when their integration branch is merged. Keep main, master, prototype/ and research/ branches, and each branch without a merged PR (list those for the owner).
- After a merge to main: the session start says so (it also names local branches whose remote branch is gone). Run /improve-codebase-architecture and /retro; their findings become tickets or a PR, not direct edits on main.
- The owner says release (or tags a version): run the release skill.
- /implement-spec: the feature branch is the integration branch, one worktree per ticket. Remove the worktrees at the end.
- prototype/<name> and research/<name> branches: push them, never merge them, never open a PR for them. Link them from the ticket.
- code-review compares against the merge-base with main (git diff main...HEAD).
- A fix commit and its PR state the cause that turned out right.


Characters
Never write the em dash character (U+2014). Not in code, docs, commit messages, PR text or replies.
Use "-", ":" or a new sentence. A hook lints every file you write.


Prompting other agents
Goal and what is ruled out, absolute file paths, one narrow task, expected output and format, read-only unless I said otherwise. No --bare on claude -p. Check the result yourself. Skill: prompting-claude-and-codex.


Rule order
- These rules and the gates win over the OMC and OMX text in the same files, and over plugin defaults.
- A repo's AGENTS.md "## Project rules" may add or tighten rules for that repo. It never loosens these rules. On a conflict, ask the owner.

Skills
- Which skill, flow or command fits a task, or how a skill works: load the skills-guide skill first. It covers the 27 Matt Pocock skills and their overlaps with OMC (Matt first). Owner guide with full scenarios: ~/.dotfiles-ai/docs/GUIDE.md.
- Every project has the full setup (tier long). A Matt skill that is not linked in this repo: read its SKILL.md from the path in skills-guide, and suggest ai-adopt --skills.

Other agents
claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>"; opencode run "<task>" --format json. Hermes never hands work to Claude. Details: ~/.config/ai/rules/<tool>.md.


## Routing table (L0)
Generated by ai-render from ai/routing.yaml v4. Do not edit here.
No label = nudge: do it unless it clearly does not apply. gate = blocked until the condition is met.
opt-in = only where the project enabled the tool (ai-start, ai-adopt).

| Rule | When | Do |
|---|---|---|
| project-knowledge | session start in a code repo | Read the Map and Libraries of this repo's AGENTS.md first, then search narrowly. (status line: memories, graph, docs map) |
| no-ai-base | session start: repo without .ai/base-version | No AI base or Map here. Suggest the owner runs ai-adopt. |
| merge-review | session start: main moved since the last review | /improve-codebase-architecture, then /retro; findings as tickets or a PR; then git rev-parse main > .ai/last-review. |
| legacy-memory | session start: old Claude memory files exist | Move the facts into the repo (PR), then delete the files. |
| upgrade-review | session start: AI tools upgraded since the last review | Run the upgrade-review skill. |
| nav-first | first broad code search (Grep, rg, grep -r, find); denied once where a graph exists | graphify query (where, how) or graphify affected (impact) first, then Serena find_symbol / find_referencing_symbols; rg only for text. |
| knowledge-check | after a git commit | Update the AGENTS.md Map, run ai-libs --sync or graphify update, as the commit needs. |
| audit-before-install (gate) | before a package install command | agent-audit this package first. No @latest, no curl-to-shell. |
| secret-scan (gate) | before git commit or push | Secret scan found a key, token or password. Remove it before commit or push. |
| no-sudo (gate) | any sudo, su, doas, pkexec | No sudo for agents: give the owner the exact command. Server box work: the box MCP tools, or outside a sandbox plain proj-agent <subcommand>. |
| no-destroy (gate) | rm -r of data, home or repo root; force push or delete of main; reset --hard with changes; root clean -x; compose down -v; DROP/TRUNCATE of a protected DB | Give the owner the exact command and why. Rebuildable folders (node_modules, .venv, dist, build) are fine. |
| pr-rules (gate) | before gh pr create, edit or ready | PR body (pr skill template): Summary with a Mermaid diagram, Evidence (Before, After), Merge Danger (Door: one-way or two-way; Blast Radius), Docs, Changed guards (Ledger on fix PRs), author-sessions block last. |
| merge-approval (gate) | before gh pr merge, or a git push to main or master | Merge only after the ship skill and when the owner's latest message says merge or approve. No push to main or master. |
| no-verify (gate) | git commit or push with --no-verify (or commit -n) | Never skip git hooks: fix what pre-commit reports, then commit again. |
| writing-for-agents (gate) | before an edit of AGENTS.md, CLAUDE.md, CLAUDE.local.md or a SKILL.md | Load the writing-for-agents skill first (Skill tool, or read its SKILL.md), then edit. |
| diagnosing-bugs | bug or performance prompt (slow, perf, broken, debug, crash, regression; RO, RU) | Use the diagnosing-bugs skill (Skill tool) and follow its loop before you end the turn. |
| tdd | test-first prompt (tests first, tdd, red-green, failing test first; RO, RU) | Use the tdd skill (Skill tool) and follow its red-green slices before you end the turn. |
| ship (gate) | before gh pr ready | Run the ship skill first (checks, review, Evidence), then gh pr ready. |
| gh-write (gate) | gh write other than the PR commands | gh reads run freely; other gh writes ask the owner first. |
| ledger-nudge | before an edit in a regression-ledger area | docs/REGRESSIONS.md area (long tier): keep its R-IDs green, run their tests. |
| no-em-dash | after a write with U+2014 | Remove the em dash (U+2014). Use '-', ':' or a new sentence. |
| ste-sentence | Markdown sentence over 25 words | STE: 25 words max per sentence. Split it. |
| docs-lookup | prompt names a library listed in Libraries, or before a dependency-file edit | context7 query-docs with the Libraries ID (resolve only if missing), then the official docs site. (cached IDs) |
| feature-grill | feature request prompt (add, implement, build ... a feature, endpoint, page; RO, RU) | Branch <feature-slug> first; grill-with-docs (else grilling); 3+ files: to-spec, to-tickets; /implement each ticket (check-fast, verify-<app> evidence, e2e, commit; draft PR after the first). Done: ship skill, then ask the owner to merge. Trivial: skip. |
| verify-before-done | after a code edit where a verify-<app> skill exists | Before done: check-fast, then verify-<app> on the changed feature (evidence), then e2e tests. |
| seo-not-enabled | SEO prompt, project without claude-seo | claude-seo is off here. Suggest: ai-adopt --tools seo. Do not enable it yourself. |
| blog-not-enabled | blog prompt, project without claude-blog | claude-blog is off here. Suggest: ai-adopt --tools blog. Do not enable it yourself. |
| browser-not-enabled | browser prompt, project without Playwright MCP | No Playwright MCP here. Suggest: ai-adopt --tools browser. Do not install a browser tool yourself. |
| serena (opt-in) | session start, Serena on (default) | Serena is on here (no memories; the Map holds knowledge): get_symbols_overview / find_symbol for definitions, find_referencing_symbols for callers, replace_symbol_body to edit. |
| graph (opt-in) | session start, graphify on (default) | graphify is on here: graphify query for structure before rg (auto-refresh after commits, merges, checkouts). |
| omc (opt-in) | session start, oh-my-claudecode on here | oh-my-claudecode is on here (/oh-my-claudecode:... skills and agents). Keep .omc/ out of commits, except .omc/skills/. |
| seo (opt-in) | SEO prompt | claude-seo first (/seo audit <url>, /seo page <url>). Other agents: hand off to Claude if it is logged in, else follow the skill files. |
| blog (opt-in) | blog prompt | claude-blog first (claude-blog:blog routes). Post file: blog-*. Site: seo-*. Other agents: hand off to Claude if it is logged in, else follow the skill files. |
| browser (opt-in) | browser prompt (screenshot, click, e2e) | Playwright MCP (headless, isolated on servers). |
| ui (opt-in) | UI prompt or UI file | Use ui-ux-pro-max. Read design-system/<app>/MASTER.md (and the page override) first. None yet: 3 to 5 directions (--design-system, different styles) as prototype variants (?variant=); the owner picks one, then --persist. Ask before paid image generation or npx ...@latest. |
| tracker-flow (opt-in) | tickets, spec, triage, backlog prompt | to-spec, then to-tickets (if the project's skills line lists them). Tickets go in docs/tickets/<feature>/ (docs/agents/issue-tracker.md); no GitHub issues or labels without the owner. |
| domain-docs (opt-in) | glossary, domain model, ADR prompt | Use grill-with-docs / domain-modeling (GLOSSARY.md, docs/adr/). |

Tie-breaks (use the first, not the second):
- one post file, or a post to be written: claude-blog:blog-*, not claude-seo:seo-*
- URL, domain, whole site: claude-seo:seo-*, not claude-blog:blog-*
- new app or project (kickoff): grilling (grill-with-docs where linked; typed: /grill-me), not OMC deep-interview (fallback)
- deep interview, ambiguity score: OMC deep-interview, not matt grilling
- library API docs: context7 with the Libraries ID, not web search


Tools
- Unsure which tools, skills or options exist on this machine: run ai-info first (and server-info on a server).
- Opt-in per project (ai-adopt --tools <id>): seo, blog (claude-seo, claude-blog), browser (Playwright MCP), omc (servers; on everywhere on macOS), ui and others. Off in a project: suggest the command, never install it yourself. Hermes follows the claude-seo and claude-blog skill files itself; Codex and opencode too, unless Claude is logged in (Codex also needs my OK for a network run).
- OMC (on servers only where a project turned it on: ai-adopt --tools omc): plan, execute, review, verify. This file and the gates win over OMC defaults. Ponytail: smallest correct diff, never cut validation or security.
- last30days (Claude, on everywhere): what people say about a topic in the last 30 days (Reddit, X, HN, YouTube, Polymarket, web): /last30days <topic>. It sends the topic out; ask before its setup wizard or any key.
- Ready tools that are not installed: ~/.config/ai/TOOLBOX.md (audit before the first install).

<!-- generated by ai/bin/ai-render from ai/agents-md/ and ai/routing.yaml; edit those -->
