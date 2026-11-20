# E1: rules classified (origin/ai, read 2026-11-20)

Sources: `git show origin/ai:<path>` in <setup>. Render: `ai-render --profile dev-mac --out` on an archive of origin/ai. Row ids are sentence rows from <scratch>/plan-research/split.py; the classification is in <scratch>/plan-research/classify.py.

## Task 1: the always-loaded text (ai/agents-md/*.md)

Kinds: fact, hard rule, procedure, style rule, pointer, duplicate of routing row, heading, markup. The code template lines (rows 85-94) and the author-sessions block (rows 110-114) are one row each. Profile 'server' rows do not load on the dev Mac.

| # | file:line | profile | text (12 words) | kind | observable | enforced today | same text elsewhere | words | verdict | reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 00-owner.md:1 | all | Lead with the answer. Hard limit: 60 words unless I ask for ... | style rule | yes: reply text (Stop payload) | nothing | i-have-adhd plugin (same reader goal) | 21 | KEEP-TEXT | owner taste; a Stop wall on word count would loop |
| 1 | 00-owner.md:3 | all | Reporting style | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 2 | 00-owner.md:4 | all | Reports and answers to me use the writing style below, in the ... | style rule | no | nothing | 10-output-shape.md:7 | 19 | MERGE 00-owner.md:9 | same claim as 10-output-shape.md:7 |
| 3 | 00-owner.md:4 | all | Keep them short with fewer facts, not with fewer words per sentence: ... | style rule | no | nothing | - | 20 | KEEP-TEXT | judgement no check covers |
| 4 | 00-owner.md:6 | all | Keep facts exact. Never drop a unit, a version, a file path, ... | style rule | no | nothing | - | 18 | KEEP-TEXT | short, judgement |
| 5 | 00-owner.md:8 | all | Writing style | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 6 | 00-owner.md:9 | all | Write all text with the rules of ASD-STE100 Simplified Technical English: chat ... | style rule | partly: Markdown sentence length | ste-sentence nudge (Markdown only, no proof pattern) | routing ste-sentence | 20 | KEEP-TEXT | core owner style; only length is checkable |
| 7 | 00-owner.md:9 | all | STE is the controlled language that aerospace and defense manufacturers use for ... | fact | no | nothing | - | 14 | DELETE | background; a current model knows STE |
| 8 | 00-owner.md:9 | all | Its rules make sure that a tired reader who is not a ... | fact | no | nothing | - | 19 | MERGE 00-owner.md:11 | fold into "write for a tired non-native reader" |
| 9 | 00-owner.md:11 | all | Write for that tired reader. Each sentence must survive one read. | style rule | no | nothing | - | 11 | KEEP-TEXT | short judgement |
| 10 | 00-owner.md:13 | all | Standing permission | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 11 | 00-owner.md:14 | all | You have my standing permission to run every command the task needs, ... | fact | no | permission mode / managed settings decide prompts | - | 23 | KEEP-TEXT | stops "may I?" turns; settings cannot say it |
| 12 | 00-owner.md:14 | all | Keep going until a real block stops you: a gate, a denied ... | procedure | no | nothing | - | 28 | KEEP-TEXT | judgement when to stop |
| 13 | 00-owner.md:14 | all | Then give me the exact command or step. | procedure | yes: reply | nothing | 40-audit:11,13; 45-no-root:3 | 8 | KEEP-TEXT | survivor for the 'give me the command' rows |
| 14 | 00-owner.md:14 | all | The gates and the other rules in this file still apply. | fact | no | gates enforce themselves | - | 11 | DELETE | no-op: a gate applies whether the text says so or not |
| 15 | 00-owner.md:16 | all | Personal files | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 16 | 00-owner.md:17 | all | Never move, split or rewrite my personal files (shell start-up files, ~/.config, ... | hard rule | yes: Edit/Write path | nothing | - | 17 | KEEP-TEXT | "outside the task" is a judgement; a path deny would also block in-task edits |
| 17 | 00-owner.md:17 | all | A "clean up" or "commit everything" request that hits one: leave it ... | hard rule | no | nothing | - | 18 | MERGE 00-owner.md:17 first sentence | same rule, example case |
| 18 | 00-owner.md:19 | all | Project rules | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 19 | 00-owner.md:20 | all | Write a rule that belongs to one project outside the AI blocks ... | procedure | yes: diff between AI markers | writing-for-agents gate loads the skill before every AGENTS.md edit | ai-start PROJECT_RULES comment | 34 | MOVE-TO-SKILL writing-for-agents | the gate already forces this skill at the only moment it matters |
| 20 | 00-owner.md:20 | all | The AI blocks belong to the dotfiles setup, and an update refreshes ... | fact | no | nothing | - | 13 | MOVE-TO-SKILL writing-for-agents | same |
| 21 | 00-owner.md:22 | all | Code organisation | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 22 | 00-owner.md:23 | all | Before you copy a nearby approach, check it against this file. If ... | style rule | no | nothing | - | 19 | KEEP-TEXT | judgement |
| 23 | 00-owner.md:25 | all | Structure code top-down: entry points at the top, implementation details at the ... | style rule | no (review only) | nothing | - | 13 | MOVE-TO-SKILL code-review (CODING_STANDARDS.md template) | code-review reads CODING_STANDARDS.md; style for the reviewer, not every turn |
| 24 | 00-owner.md:27 | all | Put an empty line between logical blocks. Code should read like text ... | style rule | no (review only) | nothing | - | 14 | MOVE-TO-SKILL code-review (CODING_STANDARDS.md template) | code-review reads CODING_STANDARDS.md; style for the reviewer, not every turn |
| 25 | 10-output-shape.md:2 | all | Output shape | heading | no | nothing | - | 2 | DELETE | section empties when its rows merge |
| 26 | 10-output-shape.md:3 | all | Follow i-have-adhd in every reply. It is always on. | pointer | no | i-have-adhd always-on flag + SessionStart hook | i-have-adhd plugin | 9 | MERGE i-have-adhd always-on hook | the plugin injects ADHD MODE ACTIVE every session (ai/rules/i-have-adhd.md:16) |
| 27 | 10-output-shape.md:4 | all | Its list "When to break the rules" applies. | pointer | no | plugin | i-have-adhd SKILL.md:119 | 8 | DELETE | the plugin text has the list |
| 28 | 10-output-shape.md:5 | all | Turn it off for one session only when I say "stop adhd ... | pointer | no | plugin | i-have-adhd SKILL.md:19 | 13 | DELETE | the plugin says "stop adhd mode" itself |
| 29 | 10-output-shape.md:6 | all | The 60-word limit has two exceptions: the state line and the one ... | style rule | yes: reply | nothing | - | 14 | MERGE 00-owner.md:1 | one reply-length rule |
| 30 | 10-output-shape.md:7 | all | Documents, PR bodies and code comments do not use this shape. All ... | style rule | no | nothing | 00-owner.md:4,9 | 20 | MERGE 00-owner.md:9 | scope of the style rule, one line |
| 31 | 20-rtk.md:1 | all | RTK | heading | no | nothing | - | 1 | KEEP-TEXT | section label for kept rows |
| 32 | 20-rtk.md:2 | all | A hook rewrites shell commands to rtk (example: git status becomes rtk ... | fact | no | rtk-hook rewrites | - | 17 | KEEP-TEXT | explains rewritten commands and output |
| 33 | 20-rtk.md:3 | all | - Full output (security tools, debugging): rtk bypass <cmd>. | procedure | no | nothing | - | 9 | KEEP-TEXT | escape for full output; no check can know when |
| 34 | 20-rtk.md:4 | all | - A refused command: rtk pipeline explain shows the rule. Never use ... | procedure | yes: command | rtk refuses | - | 16 | KEEP-TEXT | keep first sentence; drop "--ultra-compact (removed in 1.0)": stale (7 words) |
| 35 | 20-rtk.md:5 | all | - uv run is not rewritten: write uv run rtk pytest and ... | fact | yes: command | nothing | - | 19 | MOVE-TO-CHECK agent hook (rtk-hook rewrites uv run) | a tool gap, fix the rewriter, not the reader |
| 36 | 30-code-navigation.md:2 | all | Code navigation | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 37 | 30-code-navigation.md:3 | all | - Order in a repo: the Map and Libraries sections of its ... | procedure | no | project-knowledge session line | routing project-knowledge | 15 | DELETE | no-op: CLAUDE.md @AGENTS.md already loads the Map every session |
| 38 | 30-code-navigation.md:4 | all | 1. Wide question (where, how, what breaks): graphify query "<question>" --budget 1500, ... | procedure | yes: tool calls | nav-first nudge, deny once with a graph (13 fires, 62% not followed) | routing nav-first, graph | 16 | MERGE nav-first deny message | the deny message carries the order at the moment it matters |
| 39 | 30-code-navigation.md:5 | all | 2. Exact symbol, its callers, an edit: Serena find_symbol, find_referencing_symbols, replace_symbol_body. | procedure | yes: tool calls | serena session line | routing serena | 11 | MERGE serena session line | same text at session start when on |
| 40 | 30-code-navigation.md:6 | all | 3. Text only (strings, config, logs): a narrow rg, then read only ... | procedure | yes: command | nav-first | routing nav-first | 20 | KEEP-TEXT | short, general |
| 41 | 30-code-navigation.md:7 | all | - Serena and graphify are on in every project unless .ai/enabled says ... | fact | no | session status line | routing serena, graph, project-knowledge | 21 | MERGE project-knowledge status line | the status line states on/off per repo |
| 42 | 30-code-navigation.md:7 | all | Serena down: say so, use graphify and rg, and tell the owner. | procedure | no | nothing | - | 12 | MERGE 00-owner.md:14 | generic "report a block" |
| 43 | 30-code-navigation.md:7 | all | The owner can ask you to fix or switch it off (add ... | fact | no | nothing | - | 15 | DELETE | owner knowledge, not agent work |
| 44 | 30-code-navigation.md:8 | all | - Knowledge lives in the repo only: the Map, GLOSSARY.md, docs/adr, docs/research. ... | hard rule | yes: memory writes | auto memory off (setting, 2026-11-16); legacy-memory session row | routing legacy-memory | 19 | MOVE-TO-CHECK managed settings (autoMemoryEnabled false; deny serena write_memory) | a setting cannot be ignored |
| 45 | 30-code-navigation.md:9 | all | - After a commit that adds, deletes or renames modules, update the ... | procedure | yes: commit diff vs Map | knowledge-check nudge (6 fires, 67% not followed) | routing knowledge-check | 14 | MOVE-TO-CHECK lint (ai-docs-check: a Map path that does not exist fails) | observable in the tree |
| 46 | 30-code-navigation.md:9 | all | After a dependency change, run ai-libs --sync. | procedure | yes: lockfile vs Libraries block | knowledge-check nudge | routing knowledge-check | 7 | MOVE-TO-CHECK lint (make check: ai-libs --check, libs_stale() exists in ai-start:990) | observable in the tree |
| 47 | 30-code-navigation.md:9 | all | Never put secrets or personal data in AGENTS.md. | hard rule | yes: staged diff | secret-scan gate; ai-start knowledge_secret_hits | 40-audit:6 | 8 | MERGE secret-scan gate | gate covers AGENTS.md like any file |
| 48 | 30-code-navigation.md:10 | all | - Library, SDK, API or CLI code: look up docs before you ... | procedure | yes: context7 calls | docs-lookup nudge (107 fires, 80% not followed) | routing docs-lookup, tiebreak; context7 MCP server instructions | 14 | MERGE context7 MCP server instructions | the MCP server already ships this trigger every session |
| 49 | 30-code-navigation.md:10 | all | Use context7 query-docs with the ID from the Libraries section (resolve-library-id only ... | procedure | yes: context7 calls | docs-lookup nudge | routing docs-lookup; AGENTS.md Libraries block | 17 | MERGE AGENTS.md Libraries block header | the ID lives next to the library |
| 50 | 30-code-navigation.md:10 | all | If context7 has nothing: the official docs site, then the library source, ... | procedure | no | nothing | - | 15 | KEEP-TEXT | short fallback order |
| 51 | 30-code-navigation.md:10 | all | No general web search for docs (Codex too). | hard rule | yes: WebSearch calls | nothing | tiebreak library API docs | 8 | KEEP-TEXT | short; a WebSearch deny would block legitimate research |
| 52 | 30-code-navigation.md:10 | all | No secrets or private code in a docs query. | hard rule | yes: query text | nothing | - | 9 | MOVE-TO-CHECK agent hook (secret patterns over mcp context7 query args) | hooklib secret patterns already exist |
| 53 | 30-code-navigation.md:11 | all | - GitHub: the gh CLI, read-only (view, list, diff, checks) unless I ... | hard rule | yes: command | gh-write gate (ask, 6) | routing gh-write | 16 | MERGE gh-write gate | gate asks on every gh write |
| 54 | 30-code-navigation.md:11 | all | Exception: the git workflow below (push the feature branch, draft PR, gh ... | hard rule | yes: command | pr-rules, merge-approval, ship gates | 55-git-workflow.md | 21 | MERGE gh-write gate message | gate text names the PR exceptions (hooklib.py:1625) |
| 55 | 30-code-navigation.md:11 | all | A PR follows the pull request rules below. | pointer | no | nothing | - | 8 | DELETE | no-op cross reference |
| 56 | 40-audit-before-use.md:2 | all | Audit and gates | heading | no | nothing | - | 3 | KEEP-TEXT | section label for kept rows |
| 57 | 40-audit-before-use.md:3 | server | - Before you install a package, MCP server, skill or plugin: agent-audit ... | hard rule | yes: command | audit-before-install gate (server; 1 deny) | routing audit-before-install | 17 | MERGE audit-before-install gate message | gate blocks these commands |
| 58 | 40-audit-before-use.md:3 | server | Exit 3 = a scanner could not run: no PASS, not a ... | fact | yes: exit code | agent-audit | - | 13 | MERGE agent-audit output | the tool should print what exit 3 means |
| 59 | 40-audit-before-use.md:3 | server | A finding means stop and show it to me. | hard rule | yes: command | audit-before-install gate (server; 1 deny) | routing audit-before-install | 9 | MERGE audit-before-install gate message | gate blocks these commands |
| 60 | 40-audit-before-use.md:3 | server | Exact versions only, no @latest, no curl piped to a shell. | hard rule | yes: command | audit-before-install gate (server; 1 deny) | routing audit-before-install | 11 | MERGE audit-before-install gate message | gate blocks these commands |
| 61 | 40-audit-before-use.md:4 | server | - A skill or plugin with a skill-scanner HIGH or CRITICAL finding ... | hard rule | yes: exit code | agent-audit exit 4, install.sh | - | 24 | MERGE install.sh refusal | install.sh refuses already |
| 62 | 40-audit-before-use.md:4 | server | Only the owner can skip the scan (install.sh --skip-scan <tool>); never add ... | hard rule | yes: command | nothing | - | 15 | MOVE-TO-CHECK agent hook (deny install.sh --skip-scan) | one regex |
| 63 | 40-audit-before-use.md:5 | all | - Never git add -A or git add . blindly: git status ... | hard rule | yes: command | nothing | - | 20 | MOVE-TO-CHECK agent hook (deny git add -A/./--all; name files) | observable command |
| 64 | 40-audit-before-use.md:5 | all | Sandbox placeholder files in project roots are ignored globally; a real new ... | fact | no | git prints the -f hint | - | 19 | DELETE | git itself says "use -f" for an ignored path |
| 65 | 40-audit-before-use.md:6 | all | - Never commit a key, token or password. The secret-scan gate blocks ... | hard rule | yes: commit, push | secret-scan gate (17 denies); add GitHub push protection | routing secret-scan | 18 | MERGE secret-scan gate | gate denies on a hit |
| 66 | 40-audit-before-use.md:7 | all | - Never edit .env files or print their values. New settings go ... | hard rule | yes: Read/Edit path | nothing | - | 21 | MOVE-TO-CHECK managed settings (deny Read/Edit(**/.env*), keep .env.example) | a permission deny is exact |
| 67 | 40-audit-before-use.md:8 | all | - Never deploy to production or touch a production host without my ... | hard rule | partly | nothing (no-destroy server only) | - | 17 | KEEP-TEXT | prod hosts are project facts; no generic check |
| 68 | 40-audit-before-use.md:9 | all | - A failing test is a blocker, never "pre-existing" or "expected": no ... | hard rule | yes: test run, diff | stop-check (check-fast, 0-test floor), ai-ratchet tests,skips; Done item 3 | project AGENTS.md Done 3; stop-check message | 18 | MOVE-TO-CHECK GitHub required check (make check + ai-ratchet) | local stop-check only; CI cannot be skipped |
| 69 | 40-audit-before-use.md:9 | all | Fix the code; change a test only when you are sure the ... | hard rule | no | stop-check message | stop-check.py:175 | 18 | KEEP-TEXT | judgement when a test is wrong |
| 70 | 40-audit-before-use.md:10 | server | - Commands run in a sandbox. | fact | no | sandbox | - | 6 | KEEP-TEXT | server fact |
| 71 | 40-audit-before-use.md:10 | server | A network or permission error is final too: do not try to ... | hard rule | partly | sandbox (server) | - | 30 | KEEP-TEXT | judgement on errors |
| 72 | 40-audit-before-use.md:11 | dev-mac | - A network error (timeout, connection reset): retry once, or use another ... | hard rule | partly | sandbox (server) | - | 20 | KEEP-TEXT | judgement on errors |
| 73 | 40-audit-before-use.md:11 | dev-mac | A permission error is final: do not try to get around it ... | hard rule | partly | sandbox (server) | - | 27 | KEEP-TEXT | judgement on errors |
| 74 | 40-audit-before-use.md:12 | server | - A blocked gate is final for you. | hard rule | yes | every gate deny says it (router.py:1619) | router run_gate text | 8 | MERGE gate deny message | the deny text already says "Only the owner can let it through" |
| 75 | 40-audit-before-use.md:12 | server | Only I can let it through (sudo ai-gate-skip). | hard rule | yes | every gate deny says it (router.py:1619) | router run_gate text | 8 | MERGE gate deny message | the deny text already says "Only the owner can let it through" |
| 76 | 40-audit-before-use.md:12 | server | Never try to get around it; tell me the command and why. | hard rule | yes | every gate deny says it (router.py:1619) | router run_gate text | 12 | MERGE gate deny message | the deny text already says "Only the owner can let it through" |
| 77 | 40-audit-before-use.md:13 | dev-mac | - A blocked gate is final for you: the owner runs it. | hard rule | yes | every gate deny says it (router.py:1619) | router run_gate text | 12 | MERGE gate deny message | the deny text already says "Only the owner can let it through" |
| 78 | 40-audit-before-use.md:13 | dev-mac | Never try to get around it (no other command, no other tool, ... | hard rule | yes | every gate deny says it (router.py:1619) | router run_gate text | 21 | MERGE gate deny message | the deny text already says "Only the owner can let it through" |
| 79 | 45-no-root.md:2 | server | No root | heading | no | nothing | - | 2 | DELETE | section empties: rows move to the no-sudo gate |
| 80 | 45-no-root.md:3 | server | Never run sudo or try to get root (su, pkexec, setuid tricks, ... | hard rule | yes: command | no-sudo gate (7 denies) | routing no-sudo | 14 | MERGE no-sudo gate | gate blocks |
| 81 | 45-no-root.md:3 | server | When something needs root (apt, systemctl, files in /etc), stop and give ... | procedure | yes | no-sudo gate message | routing no-sudo action | 18 | MERGE no-sudo gate message | message names the step |
| 82 | 45-no-root.md:4 | server | Box work on a server: the box tool (MCP server box: list, ... | pointer | yes | no-sudo gate message | routing no-sudo action; box MCP | 41 | MERGE box MCP server instructions + no-sudo message | 41 words of tool list the MCP already describes |
| 83 | 50-pull-requests.md:2 | all | Pull requests | heading | no | nothing | - | 2 | DELETE | section empties: the pr skill and the pr-rules gate hold it |
| 84 | 50-pull-requests.md:3 | all | The PR body follows the `pr` skill (Matt Pocock). Use this template: | pointer | yes: PR body | pr-rules gate (24 denies) | pr skill; routing pr-rules | 12 | MOVE-TO-SKILL pr | the pr skill loads when a body is written |
| 85 | 50-pull-requests.md:4 | all | ```markdown / ## Summary / <smallest visual that shows the change; a ... | procedure | yes: PR body | pr-rules gate | hooklib.py:1235 deny text | 48 | MERGE pr-rules deny message | gate prints the template on deny |
| 95 | 50-pull-requests.md:14 | all | Summary must hold a Mermaid diagram of the change. | hard rule | yes: PR body | pr-rules gate | hooklib gate_pr | 9 | MERGE pr-rules gate | gate checks each field |
| 96 | 50-pull-requests.md:15 | all | Evidence is the check-fast command and the tail of its output as ... | hard rule | yes: PR body | pr-rules gate | hooklib gate_pr | 13 | MERGE pr-rules gate | gate checks each field |
| 97 | 50-pull-requests.md:15 | all | Add Before when a test went red first. | hard rule | yes: PR body | pr-rules gate | hooklib gate_pr | 8 | MERGE pr-rules gate | gate checks each field |
| 98 | 50-pull-requests.md:15 | all | A project with a verify-<app> skill also names the skill run, its ... | hard rule | yes: run.log | verify-pr wall | hooklib pr_verify_log | 18 | MERGE verify-pr wall | wall checks the evidence |
| 99 | 50-pull-requests.md:16 | all | Door must say one-way or two-way. Blast Radius must say what can ... | hard rule | yes: PR body | pr-rules gate | hooklib gate_pr | 13 | MERGE pr-rules gate | gate checks each field |
| 100 | 50-pull-requests.md:17 | all | Also required: | hard rule | yes: PR body/diff | pr-rules (test file: deny; Docs, Changed guards, Ledger: warn) | hooklib PR_WARN_FIELDS | 2 | MOVE-TO-SKILL pr (ours: ship) | warn-only fields belong to the body-writing step |
| 101 | 50-pull-requests.md:17 | all | Docs (files, or "none, because ..."), Changed guards (each edited or removed ... | hard rule | yes: PR body/diff | pr-rules (test file: deny; Docs, Changed guards, Ledger: warn) | hooklib PR_WARN_FIELDS | 23 | MOVE-TO-SKILL pr (ours: ship) | warn-only fields belong to the body-writing step |
| 102 | 50-pull-requests.md:17 | all | R-NNN. | hard rule | yes: PR body/diff | pr-rules (test file: deny; Docs, Changed guards, Ledger: warn) | hooklib PR_WARN_FIELDS | 1 | MOVE-TO-SKILL pr (ours: ship) | warn-only fields belong to the body-writing step |
| 103 | 50-pull-requests.md:17 | all | A fix PR has a test file in its diff. | hard rule | yes: PR body/diff | pr-rules (test file: deny; Docs, Changed guards, Ledger: warn) | hooklib PR_WARN_FIELDS | 10 | MOVE-TO-SKILL pr (ours: ship) | warn-only fields belong to the body-writing step |
| 104 | 50-pull-requests.md:18 | all | The author-sessions block goes at the end (next section). | hard rule | yes: PR body | pr-rules gate | hooklib gate_pr | 9 | MERGE pr-rules gate | gate checks each field |
| 105 | 50-pull-requests.md:18 | all | The pr-rules gate blocks a PR without the Mermaid diagram, Evidence, Door, ... | fact | no | pr-rules gate | routing pr-rules comment | 31 | DELETE | describes the gate; the deny says it |
| 106 | 50-pull-requests.md:18 | all | Docs, Changed guards and Ledger get a warning only. | fact | no | pr-rules gate | routing pr-rules comment | 9 | DELETE | describes the gate; the deny says it |
| 107 | 50-pull-requests.md:19 | all | In a reply or report to me, name each PR with its ... | style rule | yes: reply | pr-url Stop wall | router pr_url_stop | 22 | MERGE pr-url wall | wall blocks a bare PR number |
| 108 | 50-pull-requests.md:21 | all | PR author-sessions note | heading | no | nothing | - | 3 | DELETE | section empties: the pr skill and the pr-rules gate hold it |
| 109 | 50-pull-requests.md:22 | all | When you create a PR, or push changes to an open PR, ... | procedure | yes: PR body | pr-rules (block present, main: unknown refused) | router SESSION_MSG gives the line | 27 | MOVE-TO-SKILL ship | procedure for one moment; router injects the session line |
| 110 | 50-pull-requests.md:24 | all | <!-- author-sessions / updated: <YYYY-MM-DD> / main: <session-id> dir: <cwd, with ~ ... | procedure | yes: PR body | pr-rules partial | - | 31 | MOVE-TO-SKILL ship | same |
| 115 | 50-pull-requests.md:29 | all | main is your own session. Get the ID with herdr agent get ... | procedure | yes: PR body | pr-rules partial | - | 17 | MOVE-TO-SKILL ship | same |
| 116 | 50-pull-requests.md:30 | all | Add one herdr line for each Herdr agent that you started or ... | procedure | yes: PR body | pr-rules partial | - | 16 | MOVE-TO-SKILL ship | same |
| 117 | 50-pull-requests.md:30 | all | Get its ID the same way with its agent name or pane ... | procedure | yes: PR body | pr-rules partial | - | 18 | MOVE-TO-SKILL ship | same |
| 118 | 50-pull-requests.md:31 | all | Do not add subagents. They resume with the main session. | procedure | yes: PR body | pr-rules partial | - | 10 | MOVE-TO-SKILL ship | same |
| 119 | 50-pull-requests.md:32 | all | On an update, keep the existing lines, add the new ones, and ... | procedure | yes: PR body | pr-rules partial | - | 14 | MOVE-TO-SKILL ship | same |
| 120 | 50-pull-requests.md:33 | all | When you edit the PR body for other reasons (for example a ... | procedure | yes: PR body | pr-rules partial | - | 17 | MOVE-TO-SKILL ship | same |
| 121 | 50-pull-requests.md:34 | all | If an ID is empty, write main: unknown (or herdr: unknown) and ... | procedure | yes: PR body | pr-rules partial | - | 19 | MOVE-TO-SKILL ship | same |
| 122 | 50-pull-requests.md:35 | all | pr-resume parses this block. Keep the line format exact: one ID, dir:, ... | procedure | yes: PR body | pr-rules partial | - | 16 | MOVE-TO-SKILL ship | same |
| 123 | 55-git-workflow.md:2 | all | Git workflow (from the Matt Pocock skills; owner 2026-11-15, merge and release ... | heading | no | nothing | - | 13 | KEEP-TEXT | section label for kept rows |
| 124 | 55-git-workflow.md:3 | all | - Every job (feature, fix, trivial change) runs in its own worktree ... | hard rule | yes: Edit path, branch | worktree-first gate (0 fires) | routing worktree-first | 27 | MERGE worktree-first deny message | deny text has the exact command (hooklib.py:2181) |
| 125 | 55-git-workflow.md:3 | all | The base is main or master, or the branch the owner names. | procedure | yes | worktree-first | - | 12 | MERGE worktree-first deny message | same |
| 126 | 55-git-workflow.md:3 | all | The slug is the same as docs/specs/<slug>.md and docs/tickets/<slug>/ (a fix: fix-<slug>). | procedure | yes: branch name | nothing | docs/agents/issue-tracker.md | 12 | MERGE docs/agents/issue-tracker.md | project doc says one branch per feature slug |
| 127 | 55-git-workflow.md:3 | all | Never commit on main or master. | hard rule | yes: commit, push | worktree-first (edits only); merge-approval (push) | - | 6 | MOVE-TO-CHECK GitHub ruleset on main + ai-precommit refuses commits on main | server side cannot be skipped |
| 128 | 55-git-workflow.md:3 | all | The worktree-first gate blocks an agent edit in an adopted repo whose ... | fact | no | - | - | 18 | DELETE | describes the gate |
| 129 | 55-git-workflow.md:4 | all | - Commit each ticket on that branch (/implement commits at the end). | procedure | yes: commits, PR state | nothing | docs/agents/issue-tracker.md (ai-start ISSUE_TRACKER_DOC) | 12 | MERGE docs/agents/issue-tracker.md | same flow already in the project doc |
| 130 | 55-git-workflow.md:4 | all | Move the finished ticket file to docs/tickets/<slug>/done/ in the same commit. | procedure | yes: commits, PR state | nothing | docs/agents/issue-tracker.md (ai-start ISSUE_TRACKER_DOC) | 11 | MERGE docs/agents/issue-tracker.md | same flow already in the project doc |
| 131 | 55-git-workflow.md:5 | all | - After the first ticket commit: push the branch and open a ... | procedure | yes: commits, PR state | nothing | docs/agents/issue-tracker.md (ai-start ISSUE_TRACKER_DOC) | 23 | MERGE docs/agents/issue-tracker.md | same flow already in the project doc |
| 132 | 55-git-workflow.md:5 | all | Push each later ticket to it. | procedure | yes: commits, PR state | nothing | docs/agents/issue-tracker.md (ai-start ISSUE_TRACKER_DOC) | 6 | MERGE docs/agents/issue-tracker.md | same flow already in the project doc |
| 133 | 55-git-workflow.md:6 | all | - Feature done: run the ship skill (make check, verify-<app>, code-review, security ... | pointer | yes: Skill call | ship gate on gh pr ready (0 fires) | ship skill description; routing ship | 19 | MERGE ship skill description | description loads every session |
| 134 | 55-git-workflow.md:6 | all | Then ask the owner. | pointer | yes: Skill call | ship gate on gh pr ready (0 fires) | ship skill description; routing ship | 4 | MERGE ship skill description | description loads every session |
| 135 | 55-git-workflow.md:7 | all | - Every PR goes through the owner. | hard rule | yes: command, owner prompt | merge-approval gate (23 denies) | routing merge-approval | 7 | MERGE merge-approval gate | gate denies without the OK |
| 136 | 55-git-workflow.md:7 | all | Merge (gh pr merge --squash --delete-branch) only after the owner's latest message ... | hard rule | yes: command, owner prompt | merge-approval gate (23 denies) | routing merge-approval | 20 | MERGE merge-approval gate | gate denies without the OK |
| 137 | 55-git-workflow.md:7 | all | Never push to main or master. | hard rule | yes: push | merge-approval gate | routing merge-approval | 6 | MOVE-TO-CHECK GitHub ruleset (block direct push to main) | server side cannot be skipped |
| 138 | 55-git-workflow.md:7 | all | The merge-approval gate enforces both. | hard rule | yes: command, owner prompt | merge-approval gate (23 denies) | routing merge-approval | 5 | MERGE merge-approval gate | gate denies without the OK |
| 139 | 55-git-workflow.md:8 | all | - After a merge (yours, or the owner's on GitHub): delete the ... | procedure | yes: branches | nothing | ship SKILL.md:46 | 30 | MERGE ship skill (after-merge step) | ship skill already holds the cleanup |
| 140 | 55-git-workflow.md:8 | all | A squash merge hides the branch from git branch --merged: check that ... | procedure | yes: branches | nothing | ship SKILL.md:46 | 24 | MERGE ship skill (after-merge step) | ship skill already holds the cleanup |
| 141 | 55-git-workflow.md:8 | all | Ticket branches go when their integration branch is merged. | procedure | yes: branches | nothing | ship SKILL.md:46 | 9 | MERGE ship skill (after-merge step) | ship skill already holds the cleanup |
| 142 | 55-git-workflow.md:8 | all | Keep main, master, prototype/ and research/ branches, and each branch without a ... | procedure | yes: branches | nothing | ship SKILL.md:46 | 19 | MERGE ship skill (after-merge step) | ship skill already holds the cleanup |
| 143 | 55-git-workflow.md:9 | all | - After a merge to main: the session start says so (it ... | procedure | yes: Skill calls | merge-review session line (4 fires, 75% not followed) | routing merge-review | 21 | MERGE merge-review session line | same text at the moment it applies |
| 144 | 55-git-workflow.md:9 | all | Run /improve-codebase-architecture and /retro; their findings become tickets or a PR, not ... | procedure | yes: Skill calls | merge-review session line (4 fires, 75% not followed) | routing merge-review | 16 | MERGE merge-review session line | same text at the moment it applies |
| 145 | 55-git-workflow.md:10 | all | - The owner says release (or tags a version): run the release ... | pointer | yes | nothing | release skill description | 13 | MERGE release skill description | description says "Use when the owner says release" |
| 146 | 55-git-workflow.md:11 | all | - /implement-spec: the feature branch is the integration branch, one worktree per ... | procedure | yes | nothing | skills-guide | 19 | MOVE-TO-SKILL skills-guide | one flow, rare |
| 147 | 55-git-workflow.md:12 | all | - prototype/<name> and research/<name> branches: push them, never merge them, never open ... | hard rule | yes: gh pr create head | nothing | - | 21 | MOVE-TO-CHECK agent hook (pr-rules: refuse a PR from prototype/ or research/) | observable branch name |
| 148 | 55-git-workflow.md:13 | all | - code-review compares against the merge-base with main (git diff main...HEAD). | fact | no | nothing | ship skill | 11 | MERGE ship skill | ship calls code-review with the base |
| 149 | 55-git-workflow.md:14 | all | - A fix commit and its PR state the cause that turned ... | hard rule | yes: REGRESSIONS.md cause: | ai-ledger --check (cause: field) | docs/REGRESSIONS.md format | 14 | MERGE REGRESSIONS.md cause field | the ledger row already demands the cause |
| 150 | 60-characters.md:2 | all | Characters | heading | no | nothing | - | 1 | DELETE | section empties |
| 151 | 60-characters.md:3 | all | Never write the em dash character (U+2014). Not in code, docs, commit ... | style rule | yes: files, PR body, reply | no-em-dash nudge (no proof), ai-docs-check --md, ai-render, ai-doctor | routing no-em-dash | 17 | MOVE-TO-CHECK git hook (ai-precommit on staged lines) + pr-rules body + Stop wall on reply | fully observable; the owner wants zero |
| 152 | 60-characters.md:4 | all | Use "-", ":" or a new sentence. A hook lints every file ... | fact | no | no-em-dash nudge | routing no-em-dash | 14 | MERGE no-em-dash lint message | the lint names the fix |
| 153 | 70-prompting-others.md:2 | all | Prompting other agents | heading | no | nothing | - | 3 | DELETE | section empties |
| 154 | 70-prompting-others.md:3 | all | Goal and what is ruled out, absolute file paths, one narrow task, ... | pointer | no | nothing | prompting-claude-and-codex skill description | 21 | MERGE prompting-claude-and-codex skill | skill description triggers on every brief |
| 155 | 70-prompting-others.md:3 | all | No --bare on claude -p. | hard rule | yes: command | nothing | 80-tool-catalog:12 | 5 | MOVE-TO-CHECK agent hook (deny claude -p --bare) | one regex |
| 156 | 70-prompting-others.md:3 | all | Check the result yourself. | pointer | no | nothing | prompting-claude-and-codex skill description | 4 | MERGE prompting-claude-and-codex skill | skill description triggers on every brief |
| 157 | 70-prompting-others.md:3 | all | Skill: prompting-claude-and-codex. | pointer | no | nothing | prompting-claude-and-codex skill description | 2 | MERGE prompting-claude-and-codex skill | skill description triggers on every brief |
| 158 | 80-tool-catalog.md:2 | all | Rule order | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 159 | 80-tool-catalog.md:3 | all | - These rules and the gates win over the OMC and OMX ... | fact | no | nothing | 90-tools:6 | 21 | KEEP-TEXT | precedence; no check |
| 160 | 80-tool-catalog.md:4 | all | - A repo's AGENTS.md "## Project rules" may add or tighten rules ... | fact | no | nothing | ai-start PROJECT_RULES comment (invisible: Claude strips HTML comments) | 15 | KEEP-TEXT | precedence; the project copy is an HTML comment the model never sees |
| 161 | 80-tool-catalog.md:4 | all | It never loosens these rules. | fact | no | nothing | ai-start PROJECT_RULES comment (invisible: Claude strips HTML comments) | 5 | KEEP-TEXT | precedence; the project copy is an HTML comment the model never sees |
| 162 | 80-tool-catalog.md:4 | all | On a conflict, ask the owner. | fact | no | nothing | ai-start PROJECT_RULES comment (invisible: Claude strips HTML comments) | 6 | KEEP-TEXT | precedence; the project copy is an HTML comment the model never sees |
| 163 | 80-tool-catalog.md:6 | all | Skills | heading | no | nothing | - | 1 | KEEP-TEXT | section label for kept rows |
| 164 | 80-tool-catalog.md:7 | all | - Which skill, flow or command fits a task, or how a ... | pointer | yes: Skill call | winner gate | skills-guide description | 19 | MERGE skills-guide skill description | description loads every session |
| 165 | 80-tool-catalog.md:7 | all | It covers the 27 Matt Pocock skills and their overlaps with OMC ... | pointer | yes: Skill call | winner gate | skills-guide description | 14 | MERGE skills-guide skill description | description loads every session |
| 166 | 80-tool-catalog.md:7 | all | Owner guide with full scenarios: ~/.dotfiles-ai/docs/GUIDE.md. | pointer | no | nothing | - | 6 | DELETE | owner document, not agent work |
| 167 | 80-tool-catalog.md:8 | all | - Every project has the full setup (tier long). | fact | no | nothing | ai-start TIER | 9 | DELETE | stale: tiers removed 2026-11-15 |
| 168 | 80-tool-catalog.md:8 | all | A Matt skill that is not linked in this repo: read its ... | procedure | yes | nothing | skills-guide | 22 | MOVE-TO-SKILL skills-guide | rare procedure |
| 169 | 80-tool-catalog.md:10 | all | Other agents | heading | no | nothing | - | 2 | KEEP-TEXT | section label for kept rows |
| 170 | 80-tool-catalog.md:11 | server | claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>"; ... | pointer | yes: command | nothing | prompting-claude-and-codex skill | 17 | MERGE prompting-claude-and-codex skill | skill lists the commands |
| 171 | 80-tool-catalog.md:11 | server | Hermes never hands work to Claude. | fact | no | nothing | ai/rules/hermes.md | 6 | KEEP-TEXT | server agent fact |
| 172 | 80-tool-catalog.md:11 | server | Details: ~/.config/ai/rules/<tool>.md. | pointer | no | nothing | - | 2 | MERGE prompting-claude-and-codex skill | pointer |
| 173 | 80-tool-catalog.md:12 | dev-mac | claude -p "<task>" --output-format stream-json --verbose (no --bare); codex exec --json "<task>". ... | pointer | yes: command | nothing | prompting-claude-and-codex skill | 14 | MERGE prompting-claude-and-codex skill | skill lists the commands |
| 174 | 85-l0.md:2 | all | <!-- AI:L0 --> | markup | no | ai-render | - | 3 | KEEP-TEXT | render marker |
| 175 | 90-toolbox-and-vendor-rules.md:2 | all | Tools | heading | no | nothing | - | 1 | KEEP-TEXT | section label for kept rows |
| 176 | 90-toolbox-and-vendor-rules.md:3 | all | - Unsure which tools, skills or options exist on this machine: run ... | pointer | no | nothing | - | 19 | KEEP-TEXT | short pointer |
| 177 | 90-toolbox-and-vendor-rules.md:4 | server | - Opt-in per project (ai-adopt --tools <id>): seo, blog (claude-seo, claude-blog), browser ... | duplicate of routing row | yes: settings | *-not-enabled nudges (seo 6/100%, blog 6/83%, browser 10/80%) | routing seo/blog/browser-not-enabled | 23 | MERGE L0 not-enabled rows | same text in the table |
| 178 | 90-toolbox-and-vendor-rules.md:4 | server | Off in a project: suggest the command, never install it yourself. | duplicate of routing row | yes: settings | *-not-enabled nudges (seo 6/100%, blog 6/83%, browser 10/80%) | routing seo/blog/browser-not-enabled | 11 | MERGE L0 not-enabled rows | same text in the table |
| 179 | 90-toolbox-and-vendor-rules.md:4 | server | Hermes follows the claude-seo and claude-blog skill files itself; | fact | no | {claude_handoff} placeholder | routing seo, blog | 9 | MERGE seo/blog row handoff text | router fills it when it applies |
| 180 | 90-toolbox-and-vendor-rules.md:4 | server | Codex and opencode too, unless Claude is logged in (Codex also needs ... | fact | no | {claude_handoff} placeholder | routing seo, blog | 18 | MERGE seo/blog row handoff text | router fills it when it applies |
| 181 | 90-toolbox-and-vendor-rules.md:5 | dev-mac | - Opt-in per project (ai-adopt --tools <id>): seo, blog (claude-seo, claude-blog), browser ... | duplicate of routing row | yes: settings | *-not-enabled nudges (seo 6/100%, blog 6/83%, browser 10/80%) | routing seo/blog/browser-not-enabled | 23 | MERGE L0 not-enabled rows | same text in the table |
| 182 | 90-toolbox-and-vendor-rules.md:5 | dev-mac | Off in a project: suggest the command, never install it yourself. | duplicate of routing row | yes: settings | *-not-enabled nudges (seo 6/100%, blog 6/83%, browser 10/80%) | routing seo/blog/browser-not-enabled | 11 | MERGE L0 not-enabled rows | same text in the table |
| 183 | 90-toolbox-and-vendor-rules.md:5 | dev-mac | Codex follows the claude-seo and claude-blog skill files itself, unless Claude is ... | fact | no | {claude_handoff} placeholder | routing seo, blog | 23 | MERGE seo/blog row handoff text | router fills it when it applies |
| 184 | 90-toolbox-and-vendor-rules.md:6 | all | - OMC (on servers only where a project turned it on: ai-adopt ... | duplicate of routing row | no | omc session line | routing omc | 18 | MERGE omc session line | same |
| 185 | 90-toolbox-and-vendor-rules.md:6 | all | This file and the gates win over OMC defaults. | fact | no | nothing | 80-tool-catalog:3 | 9 | MERGE 80-tool-catalog.md:3 | duplicate precedence line |
| 186 | 90-toolbox-and-vendor-rules.md:6 | all | Ponytail: smallest correct diff, never cut validation or security. | pointer | no | ponytail SubagentStart/SessionStart hook | ponytail plugin | 9 | MERGE ponytail plugin hook | plugin injects PONYTAIL MODE ACTIVE |
| 187 | 90-toolbox-and-vendor-rules.md:7 | server | - last30days (Claude, on everywhere): what people say about a topic in ... | pointer | no | nothing | last30days skill description | 24 | MOVE-TO-SKILL last30days (description) | skill description carries the trigger |
| 188 | 90-toolbox-and-vendor-rules.md:7 | server | It sends the topic out; ask before its setup wizard or any ... | pointer | no | nothing | last30days skill description | 13 | MOVE-TO-SKILL last30days (description) | skill description carries the trigger |
| 189 | 90-toolbox-and-vendor-rules.md:8 | all | - Ready tools that are not installed: ~/.config/ai/TOOLBOX.md (audit before the first ... | pointer | no | audit gate (server) | - | 13 | KEEP-TEXT | short pointer |

| verdict | rows (all profiles) | words (all) | rows (dev-mac render) | words (dev-mac) |
|---|---|---|---|---|
| DELETE | 19 | 189 | 18 | 187 |
| KEEP-TEXT | 44 | 513 | 41 | 471 |
| MERGE | 77 | 1177 | 60 | 922 |
| MOVE-TO-CHECK | 14 | 197 | 13 | 182 |
| MOVE-TO-SKILL | 23 | 385 | 21 | 348 |
| total | 177 | 2461 | 153 | 2110 |

### Task 1 result if every verdict is applied

- Today (dev-mac render of `origin/ai`, made with `ai-render --profile dev-mac --out`): 197 lines, 3,206 words. Of these, the parts are 2,110 words (153 rows) and the L0 table is 1,088 words (35 rows).
- KEEP-TEXT rows that stay: 41 rows, 471 words (dev-mac). Subtract 7 stale words in row 34 (`--ultra-compact (removed in 1.0)`): about 464 words.
- With the Task 2 verdicts, no L0 row stays in the always-loaded text (gates speak in their deny message; session facts come in the status line).
- Result: about 465 words and about 40 lines, which is 15% of today. That is well under the vendor target of 200 lines.
- Important finding: Claude Code strips HTML comments from memory files. The loaded copy of `<project-a>/AGENTS.md` in this session has no `<!-- AI:map START -->` markers and no Lessons or Project rules guidance. The guidance in `AGENTS.md:26` and `AGENTS.md:29` of an adopted project is invisible to the model.

## Task 2: the rule table (`ai/routing.yaml` at origin/ai, 38 rules)

Columns: id; strength; event; trigger kind; measured (6 days, one dev Mac); observable; copies (text part, skill, git hook, test case `ai/tests/cases/<id>.json`); verdict; reason. Every rule has a test case file, so the copies column lists only the other places.

| id | strength | event | trigger kind | measured | observable | copies | verdict | reason |
|---|---|---|---|---|---|---|---|---|
| project-knowledge | nudge | SessionStart | session state | no data (no proof) | no | 30-code-navigation.md:3 | KEEP-AS-SESSION-FACT | the `{knowledge_index}` status line is useful; drop "Read the Map first": `@AGENTS.md` already loads it |
| no-ai-base | nudge | SessionStart | session state | 34 fires, 76% not followed | yes (ai-adopt run) | none | DELETE | ignored 3 of 4 times; adoption is the owner's job (setup-rollout skill) |
| merge-review | nudge | SessionStart | session state (.ai/last-review) | 4, 75% | yes (Skill call) | 55-git-workflow.md:9 | DELETE | a heavy owner flow; schedule it (schedule skill or cron with claude -p), not a nudge |
| legacy-memory | nudge | SessionStart | session state (memory files) | 8, 75% | yes (files) | 30-code-navigation.md:8 | TURN-INTO-CHECK | ai-doctor FAIL while `~/.claude/projects/*/memory` has files; one migration, not a nudge per session |
| upgrade-review | nudge | SessionStart | session state (upgrades.json) | 39, 79% | yes (Skill call) | upgrade-review skill | DELETE | run the skill once from install.sh after an upgrade (claude -p), so no session pays for it |
| nav-first | nudge + deny once | PreToolUse | command regex | 13, 62% | yes (tool calls) | 30-code-navigation.md:3-7; graph, serena rows | DELETE | the deny-once costs a retry and still 62% not followed; Grep is cheap for a current model (measure first, see worth trying) |
| knowledge-check | nudge | PostToolUse | command regex (git commit) | 6, 67% | yes (tree) | 30-code-navigation.md:9 | TURN-INTO-CHECK | ai-docs-check fails on a Map path that does not exist; `ai-libs --check` in make check (`libs_stale()` exists, ai-start:990) |
| audit-before-install | gate (server) | PreToolUse | command regex | 1 deny | yes | 40-audit-before-use.md:3-4 | KEEP-GATE | real block; note its own known limit: audit.log is writable by the agent (hooks README) |
| secret-scan | gate | PreToolUse | command regex | 17 denies | yes | 40-audit:6, 30-code-navigation:9 | KEEP-GATE-BUT-MOVE | keep it; add GitHub push protection (server side) and the same scan in ai-precommit, so human and other-agent commits are covered |
| no-sudo | gate (server) | PreToolUse | command regex | 7 denies | yes | 45-no-root.md:3-4 | KEEP-GATE | the sandbox and sudoers are the boundary; the gate gives the message |
| no-destroy | gate (server) | PreToolUse | command regex | 18 denies | yes | ai/rules/no-destroy.md | KEEP-GATE-BUT-MOVE | force push and delete of main go to a GitHub branch ruleset; keep the rm/compose/DB part local |
| pr-rules | gate | PreToolUse | command regex | 24 denies | yes (PR body) | 50-pull-requests.md:2-35; pr skill | KEEP-GATE-BUT-MOVE | keep the local gate for fast feedback; add a CI workflow on `pull_request` as a required check: it also catches PRs made on GitHub or by an agent without the hook |
| merge-approval | gate | PreToolUse, UserPromptSubmit (OK) | command regex + prompt state | 23 denies | yes | 55-git-workflow.md:7 | KEEP-GATE-BUT-MOVE | "no push to main" goes to a branch ruleset; the merge OK stays local, because the agent uses the owner's token and GitHub cannot ask the owner to approve their own PR |
| worktree-first | gate | PreToolUse | file path + branch state | never fired (new 2026-11-19) | yes | 55-git-workflow.md:3 | KEEP-GATE | no data yet; shell writes are not judged (hooklib.py:2189) |
| no-verify | gate | PreToolUse | command regex | 3 denies | yes | ai-precommit docstring | KEEP-GATE | cheap; protects the git hook; CI is the backup |
| writing-for-agents | gate (require_skill) | PreToolUse | file path | no data | yes (Skill call) | skill must_use card | KEEP-GATE | cheap proof; it is also the right home for 00-owner.md:20 |
| diagnosing-bugs | nudge | UserPromptSubmit | prompt-word regex (EN, RO, RU) | no data (no proof) | yes | Matt skill description | MOVE-TO-SKILL-DESCRIPTION | the skill description already says "debug this, broken, slow"; as a stop, 6 of 6 blocks were false (routing.yaml:174) |
| tdd | nudge | UserPromptSubmit | prompt-word regex | no data; baseline 0 of 3 skill use | yes | Matt skill description | MOVE-TO-SKILL-DESCRIPTION | same; 1 of 1 stop block was false (routing.yaml:182) |
| ship | gate (require_skill) | PreToolUse | command regex (gh pr ready) | never fired | yes | 55-git-workflow.md:6; ship description | KEEP-GATE | cheap; it fires at the one moment it matters |
| gh-write | gate (ask) | PreToolUse | command regex | 6 asks | yes | 30-code-navigation.md:11 | KEEP-GATE | the parser reads stages; a permission pattern is not a boundary |
| ledger-nudge | nudge | PreToolUse | file path (ledger area) | never fired | yes | stop-check ledger note | DELETE | never fired; the ledger tests run in check-fast and `ai-ledger --check` runs in make check |
| no-em-dash | nudge (lint) | PostToolUse | tool result (content) | no data (no proof) | yes | 60-characters.md; ai-docs-check --md; ai-render; ai-doctor | TURN-INTO-CHECK | fail in ai-precommit on staged lines and in pr-rules on the body; Markdown is already covered by ai-docs-check --md |
| ste-sentence | nudge (lint) | PostToolUse | file path + tool result | no data | yes | 00-owner.md:9 | TURN-INTO-CHECK | a warning in ai-docs-check on changed lines; drop the L0 row |
| docs-lookup | nudge | UserPromptSubmit, PreToolUse | prompt libs + file path | 107, 80% | yes (context7 call) | 30-code-navigation.md:10; tiebreak; context7 MCP instructions | DELETE | the biggest miss; the context7 MCP server already injects the same trigger in every session |
| feature-grill | nudge | UserPromptSubmit | prompt-word regex (about 1,500 characters) | 20, 50% | yes (Skill call) | 55-git-workflow.md:3 | MOVE-TO-SKILL-DESCRIPTION | the best nudge, but grill-with-docs is typed_only (routing.yaml:398), so this needs a model-invocable wrapper skill with that description |
| verify-before-done | nudge | PostToolUse | tool result (edit) | 3, 0% | yes | verify-tool-exists, verify-tool-used walls | DELETE | the Stop walls now enforce the same thing |
| seo-not-enabled | nudge | UserPromptSubmit | prompt regex + state | 6, 100% | yes | 90-toolbox:5 | DELETE | never followed |
| blog-not-enabled | nudge | UserPromptSubmit | prompt regex + state | 6, 83% | yes | 90-toolbox:5 | DELETE | rarely followed |
| browser-not-enabled | nudge | UserPromptSubmit | prompt regex + state | 10, 80% | yes | 90-toolbox:5 | DELETE | "click" and "screenshot" are common words; rarely followed |
| serena | nudge | SessionStart | session state | no data | no | 30-code-navigation.md:5,7 | KEEP-AS-SESSION-FACT | merge into the project-knowledge status line ("Serena: on") |
| graph | nudge | SessionStart | session state | no data | no | 30-code-navigation.md:4,7 | KEEP-AS-SESSION-FACT | same |
| omc | nudge | SessionStart | session state | never fired | no | 90-toolbox:6 | DELETE | `.omc/` is already ignored by the managed .gitignore block (GI_LINES) |
| seo | nudge | UserPromptSubmit | prompt-word regex | never fired | yes | claude-seo skills | MOVE-TO-SKILL-DESCRIPTION | the plugin skill descriptions carry the trigger |
| blog | nudge | UserPromptSubmit | prompt-word regex | never fired | yes | claude-blog skills | MOVE-TO-SKILL-DESCRIPTION | same |
| browser | nudge | UserPromptSubmit | prompt-word regex | never fired | yes | Playwright MCP tool descriptions | DELETE | the MCP tools describe themselves |
| ui | nudge | UserPromptSubmit, PreToolUse | prompt regex + file path | 11, 82% | yes (Skill call) | AI:ui project block; Map Design line; ui-ux-pro-max description | MOVE-TO-SKILL-DESCRIPTION | the Map Design line stays as a fact |
| tracker-flow | nudge | UserPromptSubmit | prompt-word regex (ticket, spec ...) | 53, 72% | yes | docs/agents/issue-tracker.md | DELETE | the regex fires on common words; to-spec and to-tickets are typed_only; the project doc holds the rule |
| domain-docs | nudge | UserPromptSubmit | prompt-word regex | 1, 100% | yes | domain-modeling description; docs/agents/domain.md | DELETE | the skill description covers it |

Also in routing.yaml: 5 tiebreaks (routing.yaml:359-364) and the winners table (routing.yaml:372-386). The tiebreaks fire only with prompt rules; after the deletes, only "library API docs" and "deep interview" can still matter. Verdict: DELETE the tiebreaks, and keep the winners as data for the skillOverrides (next table).

### Task 2 totals

| verdict | rules | ids |
|---|---|---|
| KEEP-GATE | 7 | audit-before-install, no-sudo, worktree-first, no-verify, writing-for-agents, ship, gh-write |
| KEEP-GATE-BUT-MOVE | 4 | secret-scan, no-destroy, pr-rules, merge-approval |
| KEEP-AS-SESSION-FACT | 3 | project-knowledge, serena, graph |
| TURN-INTO-CHECK | 4 | legacy-memory, knowledge-check, no-em-dash, ste-sentence |
| MOVE-TO-SKILL-DESCRIPTION | 6 | diagnosing-bugs, tdd, feature-grill, seo, blog, ui |
| DELETE | 14 | no-ai-base, merge-review, upgrade-review, nav-first, ledger-nudge, docs-lookup, verify-before-done, seo-not-enabled, blog-not-enabled, browser-not-enabled, omc, browser, tracker-flow, domain-docs |
| total | 38 | |

Of the 15 measured reminder rules (321 fires), 11 get DELETE, 2 get TURN-INTO-CHECK and 2 get MOVE-TO-SKILL-DESCRIPTION. No rule stays as a reminder. All 8 gates with denies or asks in the period stay as gates.

### Mechanisms that enforce something but have no routing.yaml row

| mechanism | where | strength | event | trigger kind | measured | observable | copies | verdict | reason |
|---|---|---|---|---|---|---|---|---|---|
| home-folder | router.py:156-168, 181, 330-333 | deny | SessionStart, PreToolUse | session state (cwd = $HOME) | no data | yes | ai/tests/cases/_home-folder.json | KEEP-GATE | cheap; no text needed |
| R-017 no-check (payload not JSON, routing broken) | router.py:319-327, 90-101 | deny | PreToolUse | tool result (payload) | no data | yes | test_router.py | KEEP-GATE | fail closed |
| abs-path (sandbox escape by PATH copy) | router.py:394-428 | rewrite or deny (auto mode) | PreToolUse | command regex + managed settings | no data | yes | none found | KEEP-GATE | security hardening, not a rule for the model |
| winner-gate | router.py:1648-1683; routing.yaml:372-386 | deny | PreToolUse (Skill), Codex file read | tool name | no data | yes | skills-guide section 5; test_commands.py | KEEP-GATE-BUT-MOVE | write the losers as `skillOverrides: off` in the project `.claude/settings.json` (ai-start already does this for 3 OMC skills: <project-a>/.claude/settings.json); then the loser is gone and no deny round trip is needed |
| pr-url | router.py:852-884 | Stop block | Stop | tool result (reply text) | no data | yes | 50-pull-requests.md:19; pr-url.json | KEEP-GATE | observable; delete the text copy |
| verify-tool-exists, verify-tool-used | router.py:887-958 | Stop block (2 per state, 4 per chain) | Stop, SubagentStop | git state | no data | yes (run.log) | Done item 1; verify-*.json cases | KEEP-GATE | it replaces verify-before-done |
| verify-pr | hooklib.py:1232 (inside gate_pr) | deny | PreToolUse | command + run.log at PR head | no data | yes | Done item 1 | KEEP-GATE-BUT-MOVE | a CI check that run.log names the PR head SHA cannot be skipped |
| verify-commit | ai-precommit:93-111 | git pre-commit refusal | git commit | staged diff (new tests) | no data | yes | README:120 | KEEP-GATE | git hook is the right layer; note the hook exits 0 when ai-precommit is not on PATH |
| ai-precommit lint | ai-precommit:54-90 | git pre-commit refusal | git commit | staged files | no data | yes | Makefile check-fast | KEEP-GATE-BUT-MOVE | the same linters as a required CI check |
| stop-check | stop-check.py:106-179 | Stop block (2 per tree, 4 per chain) | Stop | git tree fingerprint | no data | yes | 40-audit:9; Done item 3 | KEEP-GATE-BUT-MOVE | keep for fast feedback; `make check` in CI as a required check is the part that cannot be skipped |
| stop-check recipe guard | stop-check.py:145-148 | Stop block | Stop | Makefile diff | no data | yes | Done item 3 | KEEP-GATE | it stops a weakened check-fast |
| pr-rules size warning | hooklib.py:1435 | warn | PreToolUse | PR diff | no data | yes | Done item 6 | KEEP (warning) | delete Done item 6 |
| ai-start walls (third-party repo, add-only owner text, secret in AGENTS.md, --init in $HOME) | ai-start:112-114, 175-180, 228-232, 102-105 | refusal | ai-adopt run | repo state | no data | yes | none | KEEP-GATE | tool safety, no model text |
| owner skip | router.py:1629-1645; /etc/ai/gate-skip | escape hatch | all gates | root-owned file | no data | yes | 40-audit:12 | KEEP | the text copy (40-audit:12-13) can go |

## Task 3: the project layer (`ai/bin/ai-start` at origin/ai; line counts from <project-a>)

| item | what it is | lines added | fact or rule | plain file with a relative link could replace it? | verdict |
|---|---|---|---|---|---|
| AGENTS.md `## Map` block (`upsert_map`, `build_map`, ai-start:756-812) | languages, entry points, folders, run, test | 6 in <project-a> (max 60) | fact | no: it is generated once from the repo, then edited by hand; the markers only allow `--refresh-map` | keep |
| Map `- Check:` line (`upsert_check_line`, ai-start:1318) | check-fast and check commands, measured time | 1 | fact | no, it is a fact in the Map | keep |
| Map `- Design:` line (`upsert_design_line`, ai-start:1430) | path of MASTER.md; "missing: ..." procedure | 1 (62 words) | fact + procedure | yes for the procedure part | keep the path, delete the "missing: ..." clause (copy of AI:ui) |
| Map `Library versions` pointer (`LIBS_POINTER`) | pointer to Libraries | 1 | fact | n/a | keep |
| `## Libraries` block (ai-libs --sync) | library, version, context7 ID | 0 in <project-a> (no deps) | fact | no: generated from lockfiles | keep |
| `AI:<id> v<N>` opt-in blocks (`upsert_block`, `vendor_text`, ai-start:509-528); AI:ui in <project-a> | the routing action text, per enabled tool | 3 (AGENTS.md:11-13, 62 words) | rule | yes: the skill description and `~/.config/ai/rules/<tool>.md` already hold it | delete |
| `AI:done` block (`render_done`, ai-start:1333) | 6-item Done checklist | 9 | rule | partly: it is the same in every project except the check command | delete; items 1 and 6 are enforced (verify walls, pr-rules size warning), item 3 copies 40-audit:9; move items 2, 4 and 5 into the ship skill |
| `AI:verify` block (`render_verify`, ai-start:1378) | 1 Done line for a project with its own Done section | 3 | rule | yes | delete (the verify walls enforce it) |
| `## Lessons` (`LESSONS`) | empty section with an HTML comment as guidance | 2 | rule (placeholder) | it is plain already | keep, but put the guidance in the retro skill: Claude strips the HTML comment, so the model never sees it |
| `## Project rules` (`PROJECT_RULES`, ai-start:1420) | empty section with an HTML comment | 2 | rule (placeholder) | it is plain already | keep; same comment problem |
| CLAUDE.md `@AGENTS.md` (`claude_md`) | import line | 1 | fact | it is the link | keep |
| `.ai/enabled` (`enabled_text`) | tier, skills, opt-in ids | 4 | config | no: the router reads it | keep; delete the `tier: long` line (tiers removed 2026-11-15) |
| `.ai/base-version` | routing version | 1 (local) | config | no | keep |
| Makefile `ai checks` block (`check_plan`) | check-fast and check targets | 11 | check | no | keep; make the "not on PATH: skipped" branches fail under CI, else CI passes with no checks |
| `docs/REGRESSIONS.md` (`LEDGER_TEMPLATE`) | ledger format and empty ledger | 16 | fact + format rule | it is plain already | keep |
| `.ai/ratchet.json` (ai-ratchet --init) | test, skip and lint counts | 4 | data | no | keep |
| `.ai/docs-allow` (ai-docs-check --init) | Markdown placement baseline | 7 | data | no | keep |
| `.gitignore` managed block (`gitignore_text`, ai-start:683) | tool ignores plus 2 lines per linked skill | 49 in <project-a> | config | partly: the 26 per-skill link lines could go into the global excludes that ai-start already reads (`ignore_global_excludes`, ai-start:86) | make plain (shrink to the tool folders) |
| `.claude/settings.json` (`claude_plugins_plan`) | enabledPlugins, skillOverrides | 11 | config | no: settings are the enforcing layer | keep; add the winner-gate losers here |
| `.claude/skills/<name>`, `.agents/skills/<name>` links (`skill_link_plan`) | 13 Matt skills plus callees, local | 0 committed | config | no | keep |
| `docs/agents/issue-tracker.md` (`ISSUE_TRACKER_DOC`) | where specs, tickets, maps live; branch and PR flow | 33 | rule + fact | it is plain already | keep (Matt skills read this path); it is the survivor for 55-git-workflow.md:3-5 |
| `docs/agents/domain.md` (`DOMAIN_DOC`) | GLOSSARY and ADR places | 4 | fact | plain | keep |
| `CODING_STANDARDS.md` (`CODING_STANDARDS_DOC`) | reviewer rules template | 14 | rule | plain | keep; add the two code-layout rules from 00-owner.md:25,27 |
| `.serena/project.yml` (serena project create) | Serena config | 186 | config | no (tool-owned) | keep |
| `.git/hooks/pre-commit` (`precommit_steps`) | runs ai-precommit | 4 (local) | check | no | keep; it exits 0 when ai-precommit is missing, so it can be a silent no-op |
| graphify output and hook (`knowledge_steps`) | code graph, post-commit refresh | 0 committed | data | no | keep while nav-first is measured; delete if nav-first goes and nobody runs graphify query |

## Task 4: three ranked lists

### Definitely remove (12)

1. docs-lookup nudge and 30-code-navigation.md:10 (85 words): 107 fires, 80% not followed; the context7 MCP server instructions already ask for the same thing in every session.
2. The L0 table (85-l0.md, 1,088 of 3,206 words in the dev-mac render, 35 rows): gates speak in their deny message, and most nudge rows go (Task 2).
3. 50-pull-requests.md:2-35 (418 words): the pr-rules gate (24 denies) prints the template on deny (hooklib.py:1235); the author-sessions steps go to the ship skill.
4. tracker-flow nudge: 53 fires, 72% not followed; to-spec and to-tickets are typed_only (routing.yaml:398); docs/agents/issue-tracker.md holds the rule.
5. upgrade-review session nudge: 39 fires, 79% not followed; run it once from install.sh instead.
6. no-ai-base session nudge: 34 fires, 76% not followed.
7. ui nudge and the AI:ui project block (AGENTS.md:11-13): 11 fires, 82% not followed; the Map Design line and the skill description say the same.
8. seo-not-enabled (6, 100%), blog-not-enabled (6, 83%), browser-not-enabled (10, 80%) and 90-toolbox-and-vendor-rules.md:4-5.
9. 55-git-workflow.md (398 words) except one line: copies of worktree-first, merge-approval, ship gates, the ship skill (SKILL.md:46) and issue-tracker.md.
10. verify-before-done (3 fires; the verify-tool-used wall covers it) and ledger-nudge (never fired).
11. The AI:done and AI:verify project blocks (ai-start:1333, 1378; 9 lines in each project): items are enforced or copied (40-audit:9).
12. Stale or no-op text: 80-tool-catalog.md:8 ("tier long"), 20-rtk.md:4 (`--ultra-compact`), 30-code-navigation.md:3 (the Map is already loaded), 00-owner.md:9 (STE background), 10-output-shape.md:3-5 (the i-have-adhd plugin injects it).

### Definitely move to a check (12)

1. No push, force push or delete of main or master: GitHub branch ruleset (55-git-workflow.md:3,7; merge-approval 23 denies, no-destroy 18 denies are local only).
2. Tests green, no new skips, ledger valid: `make check` plus ai-ratchet as a required CI status check (40-audit-before-use.md:9; stop-check is local, 55 s).
3. PR body template: a CI workflow on `pull_request` as a required check (pr-rules 24 denies; a PR made on GitHub skips the hook).
4. Secret scan: GitHub push protection plus the same scan in ai-precommit (secret-scan 17 denies, local only).
5. Em dash: ai-precommit on staged lines and the pr-rules body check (60-characters.md:3; the no-em-dash nudge has no proof; ai-docs-check --md covers Markdown only).
6. .env read and edit, auto memory, Serena memories: managed settings permissions (40-audit-before-use.md:7, 30-code-navigation.md:8; legacy-memory 8 fires, 75% not followed).
7. Map and Libraries freshness: ai-docs-check fails on a Map path that is gone; `ai-libs --check` in make check (knowledge-check 6 fires, 67% not followed).
8. Winner gate: `skillOverrides: off` in the project settings (ai-start already writes 3 in <project-a>/.claude/settings.json).
9. `git add -A` / `git add .`: agent hook deny (40-audit-before-use.md:5; no enforcement today).
10. `claude -p --bare` and `install.sh --skip-scan`: agent hook deny (70-prompting-others.md:3, 40-audit-before-use.md:4).
11. A PR from a prototype/ or research/ branch: pr-rules refusal (55-git-workflow.md:12).
12. Secrets or private code in a context7 query: agent hook with the hooklib secret patterns on mcp context7 arguments (30-code-navigation.md:10).

### Worth trying (8)

1. Switch off nav-first deny-once for 2 weeks and compare search and turn counts (13 fires, 62% not followed; routing.yaml:86).
2. A model-invocable wrapper skill for feature kickoff, in place of the 1,500-character feature-grill regex (routing.yaml:234; best nudge at 50%).
3. Put the Lessons and Project rules guidance in visible text or in the retro skill: Claude strips HTML comments (<project-a> AGENTS.md:26, 29).
4. Run upgrade-review as one `claude -p` job from install.sh that opens a dotfiles PR (39 session nudges, 79% ignored).
5. Make the Makefile ai checks fail under CI when ai-docs-check, ai-ledger or ai-ratchet is missing (<project-a> Makefile: "not on PATH: ... skipped").
6. Make the pre-commit hook fail, not `exit 0`, when ai-precommit is missing in an agent session (ai-start PRECOMMIT_HOOK).
7. Shrink the .gitignore block (49 lines in <project-a>) by moving the 26 per-skill link lines to the global excludes.
8. ste-sentence as a warning in ai-docs-check on changed lines, then measure if long sentences drop (no fire data today).

Not checked: the 2 newest commits beyond the local checkout were read from origin/ai only; the Codex hook file (codex-hooks.json) was not compared row by row; GitHub plan limits for rulesets on private repos were not checked.
