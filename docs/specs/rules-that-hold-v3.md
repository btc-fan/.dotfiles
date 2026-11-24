# Rules that hold, version 3: one way for each phase, forced by checks

Status: plan, not built. Date: 2026-11-24. Branch: `ai-fable`. Sections 10 and 11 come from a review on the same day.

This file replaces the design of `docs/specs/rules-that-hold-v2.md`. Version 2 stays as a record.
Version 2 had 5 blockers (it removed the owner's typed OK, and it used a global hooks path).
Version 3 starts from measurements: the owner's real prompts, 6 reference repositories, and real sessions in 2 trial projects.

## 1. What the measurements say

| Fact | Number | Source |
|---|---|---|
| Start of one session that answers "OK" | 56,880 tokens, 199 tools, 40 MCP servers, 158 skills, 23 hook processes | trial project, installed setup |
| Same session with only project settings and denied unused tools | 13,700 to 15,800 tokens, 0 agent hooks | lean trial project |
| 4 tasks (feature, fix, edit on main, unclear idea), same model | installed: 1.74 USD, 193 hook processes. Lean: 0.57 USD | 8 real sessions |
| Flow result of the 4 tasks | the same: worktree, test first, ledger line. The lean one also did the "edit on main" task, on a branch | 8 real sessions |
| Ways around the agent gate hook | 125 of 184 tries pass (here-document, brace group, forged state file) | 215 payloads |
| Ways around a git hook by a change of tool | none: git runs the hook for each tool. `--no-verify` stays, so CI must stand behind it | git design, not tested here |
| Steps of the feature path that only the model's memory holds | 10 of 18 | setup map |
| Owner prompts that name a check command | 1 of 2,543 | 89 sessions, 2 machines |
| Owner prompts that are a question or an audit | 16% to 24% | the same |
| Owner prompts about a server or a deploy | 8% to 11% | the same |
| OMC use | its agents: yes (executor, code-reviewer, security-reviewer, architect). Its 76 skills: 3 calls on one machine | the same |
| Serena calls against grep and graphify | 7 against 1,128 and 175 | one machine, 60 days |

Cost of each part at session start (measured, one part off for each run):

| Part | Tokens |
|---|---|
| claude.ai connectors | 6,300 |
| OMC (skill list, agents, MCP server) | 4,900 |
| 3 style and design plugins | 5,200 |
| 15 built-in tools that the trial denied (cron, notebook, workflow and others) | 9,300 |
| Core plugin and Serena | 9,000 |
| Global rules file (3,460 words) | about 5,000 |

What the 6 reference repositories do:

- None has a router, a hook that adds text for each prompt, or a memory store.
- Three have a commit hook that repairs format and lint, and stages the result again.
- Two have one aggregate check command, and a GitHub ruleset requires that one check.
- Three have custom lint rules or guard scripts for repeated mistakes. Two have ratchets that only go down.
- One caps the always-loaded file at 20 lines with a CI check.
- No one has a script that selects the next phase. A red check tells the agent what to do.

One fact about the skills: `grill-with-docs` is typed-only. No agent can start it. `grilling` and `domain-modeling` can be started by an agent.

## 2. The principle: three layers

1. **Text says what the owner wants.** At most 500 words for all projects. A CI check holds the limit.
2. **A skill holds a procedure that needs judgment.** It loads when it is needed: grilling, test-first, bug diagnosis, verification, review, PR text.
3. **A check holds each thing that is true or false.** It runs at the commit: it repairs what a tool can repair, then it refuses. The same command runs in CI, and GitHub requires it. A refusal prints the exact next step. This is how the setup corrects the agent.

The agent hook keeps only what git and GitHub cannot see: the owner's typed OK, a server command, a `gh` write, and a hook override in a command.
A reply is also outside git. One Stop hook keeps 2 reply checks (owner decision O6).

The owner types plain words. The owner types no check command. The agent runs the commands that the project already has: `make check-fast`, `make check`, and the new `make fix`.

```mermaid
flowchart LR
    P[owner prompt in plain words] --> A[agent]
    T[text, 500 words] --> A
    S[skill on demand] --> A
    A -->|commit| H[git hook: repair, then refuse]
    H -->|refusal with the next step| A
    A -->|push and PR| C[CI: the same check]
    C -->|red: log tail| A
    C -->|green| O[owner says merge]
    O --> M[merge, then the cleanup script]
```

## 3. The flows

| Flow | The owner says | The agent does | What forces it |
|---|---|---|---|
| Small change | "lets add ...", "I want ...", "fix it" | worktree and branch, failing test, code, `make check`, commit, push. A draft PR when the owner asked for a feature, a fix or a PR | commit hook: no commit on main, repair, red check. CI: the same check |
| Bug | "... is not working", a screenshot | `diagnosing-bugs` for a hard one. A red test before the fix | commit hook: a `fix` commit needs a test and a ledger line |
| Unclear or big idea | "idk yet", "lets think" | `grilling` and `domain-modeling` (glossary, decision records), then `to-spec`, `to-tickets` | text only. The PR size check warns when a big change has no spec |
| Ticket work | `/implement` | one ticket in a fresh session, then the small-change flow | the same as the small change |
| UI | "the page looks ..." | prototype variants, the owner picks, then the small-change flow with screenshots | PR check: UI files changed and no screenshot evidence |
| Proof in the real app | (none) | `verify-<app>`: launch, doctor, drive, evidence | PR check: app code changed and no evidence run after the last code commit |
| PR | "pr" | a script writes the fixed parts of the body. The agent writes the diagram and the merge danger | CI job `pr-text` |
| Wait for CI | (none) | `gh pr checks --watch`. Red: read the log tail, repair, push | GitHub ruleset: no merge with a red check |
| Merge | "merge", "approve 21" | `gh pr merge --squash --delete-branch` | agent gate `merge-approval`, and the ruleset |
| Cleanup | "any worktrees left?" | one script: pull main, remove the worktree and the branch, refresh the graph and the library list | the script runs after each merge |
| Question or audit | "why ...", "audit ..." | read only, a short answer | agent gate `ask-first` for a command that changes a machine |
| Server work | "connect to ...", "deploy" | plan, risk, undo. Then the typed OK. The project's own deploy skill | agent gate `ask-first`. No remote wall exists here |
| Refactor | "simplify ...", "clean ..." | `improve-codebase-architecture`, then its own PR | PR size check |
| After a mistake | "why did you ..." | `retro`: the mistake becomes a check or a lint rule in the project | the 500-word cap stops a new sentence |
| New project | "adopt this repo" | one command: Map, Makefile, git hooks, CI workflow. It prints one command for the owner (ruleset, push protection) | `ai-doctor` reports a project with no CI or no ruleset |

## 4. What a project gets, and how it grows

| Layer | Holds | Grows by |
|---|---|---|
| Machine (this repository) | the 500 words, the settings, the skills, 4 agent gates, the git hook template | a PR to this repository |
| Project, generic part | `Makefile` targets `fix`, `check-fast`, `check`. The git hooks. One CI workflow with the job `check` | the adopt command writes it once |
| Project, own part | Map, glossary, decision records, coding standards, regression ledger, `verify-<app>`, project rules | the work itself |
| Project, growth point | a `checks/` folder: one small script for each repeated mistake, called by `make check` | `retro` adds a script with a test |

A project never gets a copy of the machine rules. The 3 generic blocks in a project `AGENTS.md` go away (about 250 of 562 words in the trial project).

## 5. Overlaps that go away

| Today | Version 3 |
|---|---|
| 38 claude.ai connectors in each code session | off in code sessions |
| 76 OMC skills in the list, 4 to 5 OMC hook processes for each tool call | OMC agents stay. Its skill list and its per-call hooks are off |
| 2 style plugins add 1,700 words at session start | one reply block of about 80 words in the rules file (owner decision O3) |
| Serena loads 14 tool schemas in each session | on for a project that asks for it |
| Router rows that select a skill from prompt words | removed. The rules name the 2 skills for an unclear request |
| Format error: the hook refuses, the agent repairs, then commits again | the hook repairs and stages. No extra turn (seen in 3 of 3 trial sessions with a commit) |
| `make check-fast` skips lint when the project has no lint config | the adopt command adds the lint to the check when the tool is installed |

## 6. Tickets

Each ticket is one worktree from `ai-fable`. Each ticket ends with the full suite at exit 0.

| Ticket | Work | Done when |
|---|---|---|
| W1 git hooks | A hook template for a project: no commit on main, repair and stage, `make check-fast`, the `fix` rule, a pre-push secret scan. It runs after the hook tool of the project, when one exists. | 4 fixture repositories pass: plain, husky, pre-commit framework, worktree. The red-team script shows 0 tool changes that avoid it. |
| W2 CI and wall | The adopt command writes the CI workflow as the default. `ai-github-wall` reads the branch and the job names of the project, and switches on push protection. | A fixture project gets a workflow whose job name equals the ruleset check. `ai-doctor` reports a project with no CI. |
| W3 context diet | Count the use of each built-in tool in the session logs. Then one settings block: connectors off, unused tools denied, OMC skill list and per-call hooks off. | `ai-doctor --numbers` prints the start tokens. The number is at most 25,000. A test fails when it grows. |
| W4 rules file | Cut the global file to 500 words. Move procedures into the skills and into the refusal texts of the hooks. Add the CI cap. | The word test passes. The 4 trial tasks give the same flow result in 3 of 3 runs. The map "no rule is lost" names a home for each line. |
| W5 agent hook | Keep 4 gates and the recorder of the owner's OK. Remove the router rows, the session-start text and the reminders. Close the here-document and brace-group holes. | Hook code under 2,000 lines. The red-team script: each plain form is blocked, and the 2 holes are closed. |
| W6 scripts for fixed steps | `make fix`. A PR body script (headings, check output, session block). A cleanup script after a merge. | Each script has a test. A trial session opens a PR with no hand-written fixed part. |
| W7 growth point | `checks/` in a project, called by `make check`. `retro` writes a check with a test, not a sentence. | One real retro gives one new check in a trial project. |
| W8 proof | The 4 trial tasks as scenarios of `ai-eval`, for the installed setup and for version 3. One scenario opens a PR in a project with a remote. Then one real project. | A report with cost, time, hook processes and flow result for both setups. |
| W9 migration | The steps of section 11: version 5, the fixer for old blocks, the removal of retired settings, the hook that holds in a mixed state. | A fixture machine and a fixture project of version 4 become version 5. A second run changes nothing. The way back leaves no difference. |

Order: W1 and W2 first. They make the walls. W3 and W6 have no dependency. W4 needs W1. W5 needs W1 and W4. W7 needs W6. W9 needs W4 and W5. W8 is last.

W4 also writes the map "no rule is lost" for the hooks and the per-tool files. Section 10 is its first version.

## 7. Decisions for the owner

| Id | Question | Recommended |
|---|---|---|
| O1 | Git hooks and CI as the walls, and the agent hook for 4 gates only? | Yes. |
| O2 | claude.ai connectors off in code sessions? | Yes. A project can switch one on. |
| O3 | The 2 style plugins become one reply block of about 80 words? | The owner decides. The plugins cost about 5,000 tokens for each session. |
| O4 | OMC: keep the agents, switch off the skill list and the per-call hooks? | Yes. The logs show agent use and almost no skill use. |
| O5 | Serena on only where a project asks for it? | Yes. 7 calls in 60 days on one machine. |
| O6 | Keep one Stop hook with 2 reply checks (the full PR URL, and the name of each high-impact step that ran)? | Yes. No git hook can read a reply. |
| O7 | Keep the `nav-first` row, which denies a wide search one time and names graphify? | Yes. It is the cause of the graphify use (175 calls). W8 measures if it saves tokens. |

## 8. Limits of the evidence

- The trial project has 3 code files. A large project can behave in a different way.
- Each trial task ran one time for each setup. W8 runs each task 3 times.
- The lean trial had no verification skill, no PR and no CI. Those steps are not proven yet.
- The prompt audit read 89 sessions on 2 machines. Older sessions were not on disk.
- The hook-process counts come from the session event stream of one Claude Code version (2.1.325).

## 9. Not in this plan

- No script that selects the next phase. No reference repository has one, and a red check does this job.
- No change to the hooks of Codex, OpenCode, OMX and Hermes yet. The git hooks and CI hold for each agent. The installer gives each agent the same rules text, so W4 changes their text too.
- No change to the server profile (section 10, last row).
- No block of an agent merge by a second account. The ruleset and the agent gate stay the 2 walls.

## 10. Review: the rules that version 3 did not name

The review read the whole rule set of the `ai` branch.
It has 13 always-loaded files (2,767 words), 37 per-tool files (22,692 words), the routing file and 9 own skills.
It found 31 rule families. Version 3 named a home for 1 family in full, for 19 in part and for 11 not at all.
A rule that has no home in this table is not removed. This table gives each family its home.

| Rule family | Today | Home in version 3 |
|---|---|---|
| Reply shape: 60 words, the state line, one next action, the "skipped" line | text and 2 plugins | the reply block of the rules file (O3) |
| Simplified Technical English, no U+2014 | text, 2 nudges after a write | 2 text lines. The commit hook replaces U+2014 in staged text files. `pr-text` checks the PR body |
| A reply names a PR with its full URL, and names each high-impact step that ran | 2 Stop checks | one Stop hook with these 2 checks (O6) |
| Standing permission, the high-impact list, "prepare" and "audit" | text, gate `ask-first` | text, gate `ask-first`, the recorder of the typed OK |
| Errors: one retry for a network error. A permission error and a blocked gate are final | text | one text line |
| Personal files and `.env` files | text only | a settings entry denies an edit of `.env`. The commit hook refuses a staged `.env`. Text for personal files |
| Secrets | gate at commit and push | commit hook, pre-push hook, push protection |
| A failing test is a blocker. No test is skipped or weakened | text, a Stop check runs the fast check | the commit hook and CI run the check. The ratchet stays in `make check` |
| Worktree before the first edit | gate on the edit tools. An edit through the shell avoids it | the commit hook refuses a commit on main, for each tool |
| A draft PR only when the owner asked for a feature, a fix or a PR | text, a check in the `gh` gate | the `gh` gate keeps it |
| PR body parts and the author-sessions block | gate `pr-rules`. The `Docs` line gets a warning only | the PR body script writes them. `pr-text` requires them, the `Docs` line too |
| Ship before `gh pr ready` | gate | `pr-text` requires the evidence. The ship skill stays. The gate goes |
| Verification skill | 2 Stop walls, a commit wall, a PR gate | the commit wall and the PR check stay. The 2 Stop walls go |
| Done list and regression ledger | a block in each project, `ai-ledger --check` | the commit-msg hook for a fix, the ledger check in `make check` |
| Typed-only skills (`to-spec`, `to-tickets`, `implement`, `retro` and others) | a skill card at session start | one text line: read the `SKILL.md` file and follow it |
| Skill selection by prompt words, also Romanian and Russian | router rows | the skill descriptions. They hold these words already |
| `writing-for-agents` before an edit of a rules file | gate | the CI word cap and the skill description. The gate goes |
| Navigation order: Map, graphify, Serena, text search | text, `nav-first` denies one time | one text line. `nav-first` stays (O7) |
| Library docs from context7, no web search for docs | text, a nudge | one text line |
| RTK | a hook rewrites commands, 62 words of text | the hook stays. One text line |
| Knowledge in the repository, no agent memory | a settings entry, a nudge after a commit | the settings entry. The cleanup script refreshes the graph and the library list |
| Per-tool files | loaded on demand through a pointer | no change. The file of a removed gate goes with the gate |
| Opt-in tools (SEO, blog, browser, UI) | project settings, "not enabled" nudges | project settings. The nudges go |
| Release, prompting of other agents, upgrade review | skills | no change |
| Server profile: install audit, no root, no destroy, the git guard | on only with the server profile | no change, not in this plan |

A limit for servers: the git guard of the server profile switches off git hooks for agent calls. The commit hook of W1 does not hold there. CI and the ruleset are the walls there.

Measured in the same review:

| Fact | Number |
|---|---|
| PR bodies of this repository with each gated part (diagram, Evidence, Door, Blast Radius, sessions block) | 32 of 32 |
| PR bodies with the `Docs` line, which has a warning only | 13 of 32 |
| Reply length in 5 trial sessions of the installed setup (limit: 60 words) | 74 to 155 words. A next action in 5 of 5 |
| Reply length in 4 lean trial sessions (the file had no reply block) | 49 to 65 words. No state line |
| Calls of graphify, Serena, context7 and the edit tools in 9 trial sessions | 0. Each edit went through the shell |
| Trial sessions that opened a PR | 0. The trial projects have no remote |

## 11. Migration from the present setup

The plan reuses the present tools: the version number in the routing file, `ai-update`, the adopt command and its fixers for old text.

1. The routing file gets version 5. Today the adopt command writes the version into `.ai/base-version`, and no tool reads the value.
2. `ai-doctor` fails when the marker of a project is older than the setup.
3. Machine: `ai-update` pulls and installs. The installer removes each retired settings entry with the present undo command.
4. Projects: `ai-update --projects` runs the adopt command in each project and opens one PR for each project.
5. A new fixer removes an old generic block only when its text is unchanged. For a changed block it shows the difference and stops.
6. `## Lessons` and `## Project rules` are owner text. No tool touches them.
7. The hook folder of a repository is shared by its worktrees. The new hook runs `make fix` only when the target exists.
8. The old project hook exits 0 when its tool is missing. The tool name stays on the machine until each project has the new hook.
9. A project that uses Serena gets the Serena entry in its own settings before the machine default goes off.
10. The way back: revert the PR on the setup branch, then run `ai-update`. For a project: revert its migration PR, then run the adopt command.

Mixed states that W9 must test:

- New machine, old project: the old blocks are text and do no harm. The old hook must not fail open (step 8).
- Old machine, new project: the new hook finds no setup tool. It must still refuse a commit on main and run `make check-fast`.
- A project with no remote: no CI and no ruleset are possible. `ai-doctor` says so. The commit hook is its only wall.

