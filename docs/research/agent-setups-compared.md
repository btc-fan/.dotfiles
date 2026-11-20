# Agent setups compared: why written rules are not followed here

Date: 2026-11-20
Sources: primary only. The repos named below were read through the GitHub API and not run. The other sources are the Claude Code documentation, the Codex documentation and the state logs of this setup on one dev machine. Each claim has its source.
Status: current

Question: three public setups get their rules followed with little agent configuration. What do they do that this setup does not do, and which changes follow?

## Short answer

The three setups write a rule as a check that fails. This setup writes most rules as text and reminds the agent.

1. They keep the always-loaded text small: 66 to 1,758 words. This setup loads 3,206 words with 83 instructions.
2. They ship 0 agent hooks. Their hard rules live in CI, in git hooks and in lint rules. Each session, each agent and each person gets the same answer.
3. Their project layer is plain committed files. A clone is enough. This setup needs an install on each machine, and its copies go stale (R-018).

The measured result here: the agents did not follow 75% of the reminder rules. A reminder is advice. A check is a gate.

## The sources

| Setup | What it is | Source |
|---|---|---|
| pstack | The plugin of the author of the verification skill: 58 skills, 2 agents | https://github.com/cursor/plugins/tree/main/pstack |
| verification-skill-example | One generated verification skill: 36 files, 34 feature files | https://github.com/poteto/verification-skill-example |
| kody | One product repo with 8 skills, a control CLI and a PR recap skill | https://github.com/kody-hq/kody |
| trezor-suite | A large monorepo with 41 skills and 22 nested instruction files | https://github.com/trezor/trezor-suite/tree/develop/skills |

## Table: the four setups

| Item | pstack | kody | trezor-suite | This setup |
|---|---|---|---|---|
| Always-loaded words | about 115 | 66 | 1,758 | 3,206, plus the project file |
| Instructions in that text | 0 | 0 | about 147 sentences | 83 |
| Agent hooks | 0 | 0 | 0 | 12 hook commands, 5,628 lines of router code |
| Rules as reminders | 0 | 0 | 0 | 27 of 38 |
| Hard rules live in | none | CI (1 required check), 2 git hooks, 16 lint rules | CI (10 required checks), 11 lint rules | 11 command gates in the agent hook |
| Skills | 58, typed only | 8, about 300 words each | 41, median 408 words | 9 own, about 940 words each |
| Project layer | skill files | plain files | plain files and symlinks | generated blocks, links with absolute paths |
| Limit on the always-loaded file | none | CI fails above 20 lines | none | 30 KB (the file is 19 KB to 21 KB) |

kody states its rule in `docs/contributing/harness-engineering.md`: "Prefer a failing check over another paragraph of advice."
trezor-suite states the same in `skills/performance-complexity/SKILL.md`: "Anything a linter could decide belongs in `noRestrictedSyntax` or the `eslint-local-rules` directory instead."

## What the vendors say

- Claude Code: an instruction file is "context, not enforced configuration". The target is "under 200 lines". "Longer files consume more context and reduce adherence." https://code.claude.com/docs/en/memory
- Claude Code: "If something has to happen every time, make it a hook, a deny rule, or a managed setting." https://code.claude.com/docs/en/best-practices
- Claude Code: a Bash permission rule "isn't a security boundary around the program". https://code.claude.com/docs/en/permissions
- Claude Code: a hook that fails or passes its timeout does not block the call, unless its entry has `"onFailure": "block"`. https://code.claude.com/docs/en/hooks
- Codex: "Treat tool hooks as a useful guardrail, not a complete enforcement boundary." The sandbox is the boundary. https://learn.chatgpt.com/docs/hooks

## What the logs of this setup say

Measured on one dev machine, 2026-11-14 to 2026-11-20, from `fired.jsonl`, `misses.jsonl` and `gates.log` in the state folder.

| Fact | Number |
|---|---|
| Reminder rules with a proof pattern: fires, then misses | 321 fires, 241 misses (75%) |
| The same for Codex | 18 fires, 18 misses |
| Worst reminder: `docs-lookup` | 107 fires, 86 misses |
| Reminders with no way to check obedience | 9 of 27 |
| Rules that guess the intent from prompt words | 13 |
| Gate denies | 93, and 16 of 34 session and gate pairs had 2 or more denies |
| Hook commands that Claude loads from all plugins | 50 |
| Files in one rule change (median of 6 pull requests) | 9.5 files in 6 layers |

A miss means: the rule fired, and no tool call or text in that turn matched its proof pattern. The logs do not say if the agent ignored the rule or if the rule fired on the wrong prompt.

## Why the rules fail here

1. **A reminder is not a check.** 27 of 38 rules only add text to the context, and 0 of them block.
2. **The hard rules sit in the agent session.** A command pattern in a hook misses other forms of the same command. A hook also runs per machine, from a copy that can be old.
3. **The same rule lives in many places.** The text, the table row, the hook code, the tests and the docs each hold a copy. One change touches 6 layers.
4. **The always-loaded text grew.** The doc `docs/AGENTS-MD.md` gives a target of 12 KB. The file is 19 KB to 21 KB.
5. **Nothing shows what runs.** No output has a version. Before R-018, a merged gate was off and each check passed.

## What this setup lacks

| Gap | Seen in | Ticket here |
|---|---|---|
| The tests run on each pull request | kody, trezor-suite | `docs/tickets/setup-audit/05-ci-for-the-ai-branch.md` |
| A server rule that requires a pull request and the checks | kody, trezor-suite | none: an owner step in the repo settings |
| A small always-loaded file with a limit that only goes down | kody | `docs/tickets/setup-audit/04-context-budget-check.md` |
| Fewer prompt-word reminders | all three have none | `docs/tickets/setup-audit/03-prompt-word-nudges.md` |
| A gate that blocks when it cannot answer; no hook process for tools without a rule | Claude Code docs | `docs/tickets/setup-audit/14-narrow-hook-wiring.md` (2 boxes done in this change) |
| A feature map that a check reads | kody | `docs/tickets/setup-audit/08-executable-feature-map.md` |
| The risk of a change from a script | kody | `docs/tickets/setup-audit/09-risk-classes.md` |
| A linter for agent text (one pattern file for the em dash and the like) | kody | none |
| One unit for each rule: text, check and tests together | none of the three needs it | none |
| A project layer of plain files with relative links | trezor-suite | none |
| One command that replays a hook payload and prints the decision path | none | none |

## What this setup has and the others lack

- A measure of obedience: the miss log. None of the three can say how often its agents follow a rule.
- An installer for many projects and for two agents.
- Agent-side gates for the time before a push: a secret scan, a merge OK, a check of the PR text.
- Proof that is bound to a commit (`run.log` with `commit:` and `finished:`).

## The verification skill: original and adaptation

The original generator has 44 lines and 0 lines of enforcement. A person names the skill in the prompt and reads the proof. Its evidence is not committed.
The adaptation here has 117 lines in the generator and a contract file of 176 lines. It adds 305 lines of hook code, 248 lines of tools and 1,286 lines of tests.
The added parts give a real gain (no typing, proof bound to a commit). They also carry a cost: committed evidence needs a prune tool, and a public repo then shows run data.

## Order of work

The order follows one rule: move a rule down to the lowest layer that can check it, then delete its text.

1. Done in this change: `ai-sync` refreshes the hook copy that Claude runs (R-018). The PreToolUse entry blocks when the router fails.
2. Owner step: a ruleset on the default branches of the repo (require a pull request, require the checks).
3. Ticket 05: the suite runs on each pull request.
4. Ticket 03: remove or merge the prompt-word reminders. Start with those above 75% misses.
5. Ticket 04: lower the limit of the always-loaded file after each cut, and never raise it.
6. New tickets for the gaps without one: the agent-text linter, one unit for each rule, the plain-file project layer, the replay command.

## Not checked

- A real Codex session.
- Server installs with managed hooks.
- How often the agents of the three setups follow their text rules: none of them measures it.
- The body text of most skills in pstack and trezor-suite.
