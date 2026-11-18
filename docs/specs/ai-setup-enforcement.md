# Spec: AI setup enforcement

Status: agreed with the owner on 2026-11-16 (grilling session, questions Q1 to Q37). Open items are in "Further notes".

## Problem Statement

The owner built one AI setup for every project: generic rules, MCP servers, plugins, skills and gates. `ai-adopt` puts it into a repo. The idea is that, after adoption, the agents follow the rules.

In real sessions the agents do not follow most of the rules. The install is complete (`ai-doctor`: 113 pass, 0 fail), but:

1. Skills are almost never used. In 7 days all sessions used 3 skills in total.
2. Most rules are text or nudges. Text in CLAUDE.md and AGENTS.md is advisory: when two texts conflict, the model picks one.
3. Routing v4 removed the per-action nudges for Serena, graphify and agent docs. After that, nothing reminds the agent at the moment of the action.
4. 10 skills that the rules require are typed-only. The agent cannot call them and does not see their description.
5. OMC and OMX add about 85 and 24 skills. They duplicate our skills, and `skillOverrides` cannot hide plugin skills. The skill list is over its budget, so descriptions are dropped.
6. Some parts are broken or noisy: the RTK hook causes "no verdict" denials in auto mode, the global auto mode environment describes another repo, the router asks its L2 question on agent notifications, `docs-lookup` fires on prompts that are not about a library, and the PR author-sessions block needs a CLI that is not on PATH.

## Solution

Keep the same tools. Move every rule that matters from text to a mechanism that runs at the moment of the action, for Claude Code and Codex together:

- Gates (PreToolUse deny, Stop block) for the few rules that must never be skipped.
- Short always-on context (SessionStart injection, like i-have-adhd and Ponytail) for the rules the agent must know before it acts.
- A winner rule: when two skills do the same job, one wins and the agent cannot call the other one.
- Measurement: `ai-doctor` shows which skills and rules were used and missed.

Then prove it with tests on 4 levels, on fixture repos that include the edge cases (empty repo, docs-only repo, code repo, existing project, folder without git).

## User Stories

1. As the owner, I want context7 and Serena (MCP) and graphify (CLI) on by default in every project, so that every agent has docs and code navigation without setup.
2. As the owner, I want every MCP, gate and skill decision to apply to Claude Code and Codex together, so that the two agents behave the same.
3. As the owner, I want Playwright and box to stay opt-in, so that projects that do not need them stay small.
4. As the owner, I want dropped tools (GitHub MCP, Grounded Docs, byterover, caveman-shrink, OMC exa) to stay dropped, so that the setup does not grow back.
5. As the owner, I want the first broad text search of a session in a code repo with a graph to be denied once with "run graphify query first", so that the agent uses the graph before it greps.
6. As the owner, I want `docs-lookup` to fire only when the prompt names a library from the repo's Libraries block, or before an edit of a dependency file, so that the rule is not noise.
7. As the owner, I want OMC and OMX to stay on everywhere, because I use them all the time.
8. As the owner, I want my global rules and my project rules to win over OMC and OMX text, so that the orchestration tools work inside my rules.
9. As the owner, I want a winner gate: when the agent calls a skill that loses in the overlap table, the call is denied and the message names the winner.
10. As the owner, I want OMC and OMX to win the jobs that my skills do not cover (autopilot, ralph, team, ultragoal, ask, babysit, fix-ci, cancel).
11. As the owner, I want my own typed `/name` call to never be blocked by the winner gate, so that my choice always wins.
12. As the owner, I want Ponytail and i-have-adhd to stay global and injected every session.
13. As the owner, I want ui-ux-pro-max to stay on by default per project, with `no-ui` to switch it off.
14. As an agent, I want the router to give me the SKILL.md path of a typed-only skill and tell me to read and follow it, so that I can use all 10 typed-only skills without a Skill call.
15. As an agent, I want a skill card at session start (under 1.5k characters) that lists the must-use skills with one trigger line each, so that I know them before my first action.
16. As the owner, I want an edit of AGENTS.md, CLAUDE.md, CLAUDE.local.md or a SKILL.md to be blocked until `writing-for-agents` is loaded or read in the session.
17. As the owner, I want the agent to be unable to end its turn on a bug or performance prompt ("slow", "performance", "broken", "debug") until `diagnosing-bugs` was used, once per session.
18. As the owner, I want `gh pr ready` to be blocked until the `ship` skill ran in the session.
19. As the owner, I want `ai-doctor` to show per-skill use for 30 days and the misses of gated skills, so that I can see if the setup works without reading transcripts.
20. As the owner, I want the 4 git gates (secret-scan, pr-rules, merge-approval, no-verify) to stay as they are.
21. As the owner, I want the git workflow to stay as written: branch per feature slug, draft PR after the first ticket, ship, `gh pr ready`, owner merge, no push to main, prototype and research branches never merged.
22. As the owner, I want the herdr CLI on PATH so that the PR author-sessions block gets real IDs, and the router to fill `main:` from the hook payload when herdr is missing.
23. As the owner, I want `gh` write commands other than the PR commands to ask me first.
24. As the owner, I want one workflow for every repo, also for a docs-only repo.
25. As the owner, I want `ai-adopt` to create a `make check` in every repo (in a docs-only repo: Markdown placement, em dash, links), so that `ship` works everywhere.
26. As the owner, I want `~/.claude/CLAUDE.md` to hold only the import of my root rules, the machine line and a 3-line OMC note, so that no long vendor text competes with my rules.
27. As the owner, I want RTK to skip its rewrite when the permission mode is auto, so that auto mode reviews the real command.
28. As the owner, I want the auto mode environment of one repo to live in that repo, not in the global settings.
29. As the owner, I want the router L2 question to fire only on my prompts, not on agent notifications.
30. As the owner, I want `ai-adopt` to set up an empty git repo and a docs-only repo fully, so that a project that starts empty is ready.
31. As the owner, I want `ai-adopt` to refuse a folder that is not a git repo unless I pass `--init`, so that it never adopts my home folder by mistake.
32. As the owner, I want the graph to be built and the Serena and graph rules to switch on at the next session start after the first code file appears, without a new `ai-adopt`.
33. As the owner, I want a baseline measurement before any change, so that each PR shows a before and after number.
34. As the owner, I want each change proven by tests on 4 levels before I merge it.
35. As the owner, I want an independent audit after each phase and at the end, so that the setup gets better over time and I can trust it for any new project.
36. As the owner, I want the Mac rollout proven for 7 days before the same rollout on the home server.

## Implementation Decisions

Mechanisms (the same on Claude Code and Codex where the agent supports it):

- **Router rules** stay the single source of "which tool, when" (`routing.yaml`). New fields:
  - `require_skill: <name>`: a rule passes only when the session has a proof for that skill: a Skill call, a typed `/name` (UserPromptExpansion), or a Read of its SKILL.md.
  - `strength: stop`: a Stop hook block (once per session per rule) in place of a PreToolUse deny.
- **Winner gate**: one table, the overlap table in the skills guide, becomes data for the router. A PreToolUse hook on the Skill tool denies a losing skill and names the winner. A typed `/name` is not affected, because typed calls do not go through the Skill tool.
- **Typed-only skills**: the existing "read and follow" hint (commit 7eda4c4) extends from 4 to all 10 typed-only skills. Upstream skill files stay unchanged.
- **Skill card**: one SessionStart injection, rendered from the routing data, reinjected after compact and clear.
- **Graph-first gate**: deny once per session the first broad search in a code repo that has a graph. Text searches after that pass.
- **gh gate**: read subcommands pass; PR subcommands go through the existing gates; other writes ask.
- **RTK**: the hook reads `permission_mode` from the hook input and does not rewrite in auto mode. If RTK cannot do this, the fallback is to drop the automatic rewrite.
- **CLAUDE.md**: the installer writes the short form. OMC setup must not grow it back (`ai-doctor` checks it).
- **ai-adopt**: makes `make check` in every repo, handles empty and docs-only repos, refuses a non-git folder without `--init`.
- **Session start**: when a repo has code and no graph, start `graphify update` in the background.
- **ai-doctor**: per-skill use over 30 days, misses of `require_skill` rules, the CLAUDE.md form, the RTK mode check, the herdr CLI.
- **Codex**: the same rules through Codex hooks (PreToolUse also covers `apply_patch`, Stop can block). OMX skills follow the same winner table.

Seams (where the tests hold the setup):

1. The router: hook input JSON in, decision JSON out. The highest seam for rules and gates.
2. The installer: `install.sh` and `ai-adopt` on a fixture repo, checked by `ai-doctor`.
3. The agent: a headless session (`claude -p`, `codex exec`) on a fixture repo, checked by the router logs and the transcript.

## Testing Decisions

A good test checks behaviour that the owner can see: a decision, a file, a log line, a tool call. It does not check internal functions.

Levels:

1. **Unit**: router cases for every new or changed rule, should-fire and should-not-fire, the same style as the existing case files and `test_router.py`.
2. **Install**: a fresh `ai-adopt` on each fixture, a second run that changes nothing, `ai-doctor` with 0 fail, and a clean uninstall. Prior art: `test_setup.py`, `test_profiles.py`.
3. **Behaviour**: headless Claude and Codex sessions run the prompts in `ai/evals` 3 times each. Pass: at least 90% of the expected skill calls, gate decisions and graphify or Serena calls appear. Prior art: `ai/evals/HOWTO.md`, `test_tier1.py`.
4. **Evolution**: a multi-session scenario that starts in an empty repo: first code, feature, PR, merge, next session. Pass: the Map is updated, the graph refreshes after the commit, the next session uses graphify and Serena on the new code, and the merge-review prompt fires.

Fixtures (made by a script, never real repos):

- empty git repo; docs-only repo; folder without git; small app with code, tests, `make check` and a `verify-<app>` skill; a throwaway copy of an existing adopted project.

Edge cases that the tests cover:

1. A second `ai-adopt` run changes nothing.
2. A repo with its own AGENTS.md, CLAUDE.md and `.claude/settings.json`: the owner text stays, only managed blocks change.
3. A linked git worktree.
4. A monorepo with 2 languages, a nested repo and a submodule.
5. A large repo: the graph build and the Serena index do not block session start.
6. A language without a Serena language server: Serena switches off cleanly.
7. `no-serena`, `no-graph` and `no-ui` in `.ai/enabled` are honoured.
8. Session resume, `/clear` and `/compact`: the skill card and the L0 table come back.
9. Subagents, OMC team workers, `claude -p` and `codex exec`: the gates fire.
10. Permission modes default, plan, acceptEdits and auto: RTK and the gates behave as agreed.
11. A router internal error: Bash fails closed, other tools fail open, the error is in the log.
12. A changed Codex hook (new hash): `ai-doctor` reports it.
13. No network: context7 is missing, the session does not hang.
14. The owner types `/name` of a losing skill: it runs.
15. Prompts in Romanian and Russian fire the same rules.
16. Uninstall, then install: the same result.
17. The first code file in an empty repo: the graph and Serena rules switch on at the next session.
18. The server and dev-mac profiles render their own rows.
19. An agent notification does not fire the L2 question.
20. A repo without a remote, and an `ai-adopt` run on main (see open items).

Audit and improvement: after each phase, a review of the diff in a fresh context by a different model. At the end, an audit against the goals G1 to G10 in `docs/AUDIT-BRIEF.md`. Findings become tickets.

## Out of Scope

- The claude.ai connectors from the organization settings.
- The `anthropic-skills:*` skills.
- Server-only security work (sudo, SSH, disks). The home server gets the same AI rollout in Phase 5 only.
- Changes to the upstream Matt Pocock skill files.

## Further Notes

Delivery, in order. Each PR stays under about 400 changed lines, goes through `ship`, and the owner merges it.

| Phase | Work |
|---|---|
| 0 | Test harness and fixtures, then the baseline numbers |
| 1 | PR 1: cleanup and the winner gate. PR 2: skill card, typed-only hints, ai-doctor stats |
| 2 | PR 3: skill gates and graph-first gate. PR 4: gh gate, herdr and `main:`, ai-adopt changes |
| 3 | PR 5: MCP deviations, then the evolution test |
| 4 | Re-adopt all real projects on the Mac, 7 days of ai-doctor numbers, then retro |
| 5 | The same rollout on the home server |

Open items:

1. MCP: the comparison of SPEC.md with the installed MCP servers is not finished. Its deviations become the scope of PR 5.
2. A repo without a remote (decided 2026-11-16): `ai-adopt` warns, and `ship` stops at step 1 with "no remote".
3. `ai-adopt` on main (decided 2026-11-16): `ai-adopt` commits on a branch `ai-adopt` and asks the owner to merge.
4. After the last phase: the owner's test repo gets the full setup, and the owner tests it there first.
