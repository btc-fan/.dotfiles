# Deep audit of the AI setup (2026-11-18)

Scope: the `ai` branch at `f002b8a`, as installed on the main Mac (profile dev-mac), and the project layer that
`ai-start` wrote into the folder `server-start` on 2026-11-16. Owner goal: a setup that answers short, follows
the global rules, uses the defined skills, checks its own work and follows the owner's git rules.

How to read the evidence labels:

- **measured**: a command was run for this audit and the output was read.
- **agent**: a read-only subagent reported it with file and line; it was not checked a second time.
- **docs**: the Claude Code hooks reference, read on 2026-11-18.

## 1. Summary

1. The slow session of 2026-11-18 had one main cause outside the setup: the Mac was saturated. The setup made it
   worse, because it starts 7 processes for each tool call.
2. The hooks are not obsolete. They are wired too wide. The router runs on each Bash, Read, Edit, Grep, Glob and
   Agent call, and it has work on few of them.
3. Some gates fail open and one fails closed for the wrong reason. A hook that passes its timeout does not block
   a tool call. The secret scan blocks when the machine is slow, and it tells the agent that only the owner can
   pass.
4. gitleaks added a second scan on top of the built-in one. It is the only part that timed out. The built-in scan
   alone is enough for the gate.
5. oh-my-claudecode (OMC) is the largest source of processes, of injected text and of rules that the owner did not
   write. It adds 4 of the 7 processes of a Bash call and 5 of the 7 at a Stop.
6. The check "run check-fast before the agent says done" is off on the dev-mac profile, on all 3 machines. The
   rules and the Makefile still say that the Stop hook runs it.
7. Many git rules exist only as text. No hook stops a commit on `main`, `git add -A`, an edit of `.env`, or a PR
   of 6,800 lines.
8. The project layer has one size. A folder with no code got the full layer: 15 skill links, a ledger, a ratchet,
   a Serena config and a UI rule.

## 2. Why the session was slow

All values measured on the main Mac between 22:09 and 22:42.

| Fact | Value |
|---|---|
| Load average (12 cores) | 313 at 22:28, 110 at 22:41 |
| Swap | 21.3 GB used of 22.5 GB |
| Chrome renderer processes | 110, together about 10.7 cores, 92 older than 1 day |
| Processes | 992 |
| One hook process, calm machine | 55 to 95 ms wall, 0.05 to 0.10 s CPU |
| One hook process, loaded machine | 1.5 to 5 s wall |
| `gitleaks version`, loaded machine | about 43 s wall |
| Secret-scan gate on `git push`, calm machine | 0.5 s wall, 0.41 s CPU |
| Secret-scan gate on `git push`, loaded machine | 18 to 22 s, then deny "timed out" |

Chrome was the cause. At 22:48 no Chrome renderer process was left, the load average was 6, and swap was 4.2 GB
used of 5.1 GB. What made the Chrome windows busy was not found. The setup did not cause it.

What the setup adds: each tool call starts new processes, so each call pays the start cost of the loaded
machine several times. The hooks of one event run in parallel, so the wall time is the slowest hook, not the
sum.

| Event | Hook processes | Ours | OMC | Other |
|---|---|---|---|---|
| One Bash call (before and after) | 7 | 3 (RTK, router, router) | 4 | 0 |
| One Edit call | 7 | 2 | 5 | 0 |
| One Read call | 7 | 2 | 5 | 0 |
| One user prompt | 4 | 1 | 2 | 1 (Ponytail) |
| One Stop | 7 | 2 | 5 | 0 |
| One session start | 12 | 3 | 5 | 4 (Herdr 2, Ponytail, i-have-adhd) |
| One subagent (call, start, stop) | 9 | 3 | 5 | 1 |

Evidence from the transcript of this session (agent): the router passed its 5 s timeout on a user prompt 2
times, the OMC git guard 3 times, and one RTK rewrite took 19.9 s.

## 3. Hook wiring: what is wrong

1. **No `if` filter (docs, measured).** A hook can carry `"if": "Bash(git *)"`, and then the process starts only
   for that command shape. `hooks.json` uses only tool-name matchers. The router starts for each Read, Glob,
   Agent and Task call, and no routing rule names these tools (agent: Read trace, handler 1 ms, no output).
2. **Gates fail open on a timeout (docs).** "A timed-out command hook doesn't block the tool call" unless the hook
   sets `"onFailure": "block"` (Claude Code 2.1.295 or later; installed: 2.1.325). No hook of the setup sets
   it. On a loaded machine a gate can vanish without a message.
3. **The prompt hook has 5 s.** The merge OK of the owner is stored by the prompt hook. When it times out, the
   OK is lost and the next `gh pr merge` is denied. Not checked: if the 2 timeouts seen caused a false deny.
4. **The Stop check is off but still starts.** `stop-check.py` starts at each session start and each Stop and
   returns at once on dev-mac (`PROFILE_GUARDS=0`, owner decision 2026-11-15). Measured: the newest state file is
   from 2026-11-15.
5. **No bytecode cache (agent).** The hooks set `dont_write_bytecode`, so Python compiles 4,900 lines of router
   and hooklib on each start.
6. **Dead settings (agent).** `routing.yaml` holds keys that the router never reads: `prefilter`, `timeout_s`,
   `reinject_after_compaction`, `L3_regex`, `L4_gates`, `L7_miss_log`. The tier is always "long", and the code
   for the other tiers is dead.
7. **A broken notifier (agent).** `claude-notify` hits its 12 s timeout on Stop; 6 lines in `router-errors.log`.

## 4. Secret scan: keep the built-in scan, move gitleaks out of the gate

How the gate works now (measured, `hooklib.py`): on `git commit` and `git push` it reads the diff with git, runs
gitleaks with a 10 s cap, then runs the built-in pattern scan on the same text. The total budget is 18 s. A
timeout gives a deny with the text "the owner can run: sudo ai-gate-skip".

Findings:

- All 7 secret-scan walls in `walls.jsonl` on 2026-11-18 are timeouts. None is a real key.
- gitleaks is a 21 MB unsigned binary. It needs 0.4 s CPU on a calm machine and about 43 s wall on the loaded
  machine, where Python needed 3 to 5 s. The built-in scan needs no extra process.
- A gitleaks timeout denies the commit even when the built-in scan would pass (the gitleaks call comes first).
- A missing or crashed gitleaks is ignored, so the gate already works without it (agent).
- 5 git calls build an allow-list for one key before each scan, outside the budget (agent).
- The false blocks that led to gitleaks (14 of 14 sampled) were fixed in the built-in rules too: only added lines
  are scanned, and test paths accept only real key shapes.

Recommendation: the gate uses the built-in scan only. gitleaks runs where no hook timeout exists: a git
`pre-push` hook or CI, on the pushed range. A scan that cannot finish retries once, then reports "not checked" and
names the command. It does not send the agent to a `sudo` step.

## 5. Which rules have a hook, and which are text only

| Rule in the global rules | Enforced by | Holds on dev-mac |
|---|---|---|
| No secret in a commit or push | PreToolUse gate | Yes; false blocks under load |
| PR body template | PreToolUse gate on `gh pr create, edit, ready` | Yes |
| Merge only after the owner's OK; no push to main | PreToolUse gate | Yes |
| No `--no-verify` | PreToolUse gate | Yes |
| Load writing-for-agents before an agent doc edit | PreToolUse gate | Yes; it stopped Codex in 3 of 3 eval runs |
| Ship skill before `gh pr ready` | PreToolUse gate | Yes |
| Verify the app before a commit with tests, and before a PR | git pre-commit, PreToolUse gate | Only where `ai-precommit` is the hook |
| Verify tool exists and was used | Stop and SubagentStop | Yes, in adopted repos; 2 blocks, then open |
| `check-fast` green before done | Stop hook | **No: off on dev-mac** |
| Never commit on main or master; branch first | text | No hook |
| Never `git add -A` or `git add .` | text | No hook |
| Never edit `.env` files | text | No hook |
| No deploy to production without OK | text | No hook |
| A PR stays under about 400 lines | text | No hook (PR 13: about 6,800 lines) |
| Delete merged branches and worktrees | text | No hook (2 merged local branches, 2 old worktrees found) |
| Draft PR after the first ticket; ticket file to `done/` | text | No hook |
| Answer in 60 words, telegraph style | text, 3 layers | No hook; the layers disagree |
| Use context7 before library code | nudge | Ignored in 86 of 107 fires |
| Use the tracker skills, grill before a feature | nudge on prompt words | Ignored in 33 of 42 and 9 of 18 fires |
| No auto memory; knowledge lives in the repo | Claude setting | OMC project memory is still injected |

Pattern: a rule holds when a hook reads an action or a git state. A rule fails when it is text, or when a hook
reads words in the prompt.

## 6. Collisions with the other plugins

All from the plugin inventory (agent), OMC 5.8.5, with file and line in the agent output.

1. **Walls the owner did not write.** OMC can deny a Read of a file over 1,500 lines or 45 KB after one warning
   (read budget). OMC can block a Stop when the final answer asks an option question or when changed code has a
   TODO (workflow drift guard). OMC blocks a Stop at 94 percent context.
2. **6 hooks can block one Stop:** the router, the stop check, and 4 OMC hooks. Each has a limit, so no endless
   loop. A comment in `stop-check.py` says OMC never blocks when `stop_hook_active` is set. That is false for
   2 OMC hooks.
3. **Memory against the owner rule.** OMC writes `.omc/project-memory.json` and injects it at each session start
   and after each compaction. No switch turns the injection off. In `server-start` it says the language is
   "C/C++" (it saw a Makefile).
4. **Personal file.** OMC appends each Bash command of the agent to `~/.bash_history`. Switch: `bashHistory:
   false`.
5. **Text on each call.** "Use parallel execution for independent tasks ..." on Bash, "File written. Test the
   changes ..." on Write, "Tool Bash failed ..." on a failure. `OMC_QUIET` is not set.
6. **Duplicate context.** An OMC hook injects the nearest `AGENTS.md` again after a Read or an Edit (up to 5,000
   tokens), although `CLAUDE.md` already loads it.
7. **Navigation, 3 voices.** Our rule says graphify, then Serena. Serena's server text says "call
   initial_instructions first". OMC text says "consider Grep" and its agents say "always use lsp_document_symbols".
8. **Skill names.** 6 OMC skills have the names of our skills. The 6 `skillOverrides` entries do not remove them
   from the list. The skill list is 29,971 characters for 135 skills; OMC has 76 entries (12,543 characters).
   35 OMC skills come from the pstack ideas; the setup links the pstack originals for 2 of them.
9. **Reply shape.** The global rules say 60 words. i-have-adhd injects 6,989 characters of shape rules. Ponytail
   injects 2,859 characters and asks for a closing line on skipped work. Each subagent gets the Ponytail text too.
10. **The keyword switch-off works** (`OMC_SKIP_HOOKS=keyword-detector`), but its process still starts on each
    prompt. A second context nag at 70 percent was missed by ticket 15 (35 times in one session).

OMC switches that exist: `OMC_SKIP_HOOKS` (tokens `pre-tool-use`, `post-tool-use`, `post-tool-use-failure`,
`skill-injector`, `keyword-detector`, `project-memory-posttool`, `workflow-drift-guard`, `persistent-mode`,
`subagent-tracker`), `OMC_QUIET=2`, `OMC_READ_BUDGET=off`, `OMC_GIT_GUARDRAILS=0`, `bashHistory: false`. No
switch stops the process starts or the memory injection. Only "plugin off" does.

## 7. Architecture of the setup code

From the architecture walk (agent). Size: about 20,500 lines of Python and bash, 64 test files. The most changed
files since 2026-11-10: `ai-doctor` 42 commits, `claude.sh` 33, `ai-start` 30, `hooklib.py` 29.

Friction, each with the count of places that hold the same knowledge:

| Concept | Places |
|---|---|
| "Is this repo adopted" | 2 definitions (`.ai/enabled`, `.ai/base-version`) |
| Parser of `.ai/enabled` | 6 |
| Run git and read the output | 9 copies |
| Project root | 5 |
| State folder default | 9 |
| Verify proof "newer than" rule | 3 different rules (file time, commit time, HEAD time + 1) |
| Loop limits for Stop blocks | 2 |
| Session state store | 2 (one with a lock, one without) |
| Redaction patterns | 3 sets (bash, Python, hooklib) |

Other points:

- `hooklib.py` is one module of 3,157 lines. The router imports 49 names from it.
- Code for things that are not on this Mac: the server-only gates (868 lines, with 3,739 lines of test cases),
  Hermes (about 670 lines), ai-box (438), the root layer (about 540). `routing.yaml` says dev-mac is the
  profile of all 3 machines; if that is true, only tests reach this code.
- The copies under `ai/hooks/hermes/` are generated and ignored by git. `ai-render --check` guards the drift.
- Tests: 43 case files drive the router through its real interface (hook JSON in, decision out). Other tests load
  `ai-start` and `ai-doctor` as modules and call private checks.

Candidates, strongest first (details in the HTML report of the improve-codebase-architecture run):

1. Project state as one module (adopted, enabled tools, skills, verify skill). Strong.
2. Secret scan inside one budget, built-in only. Strong.
3. Hook wiring rendered from the routing rules and the profile, with `if` filters. Strong.
4. One file per gate, loaded only when the profile uses it. Worth exploring.
5. One turn-end module: one proof rule, one loop limit, one state file. Worth exploring.
6. Shared plumbing: git, root, state folder, time. Worth exploring.
7. Remove the profiles and agents that no machine uses. Owner decision.

## 8. The project layer in server-start

Measured in `~/work/server-start`:

- The folder holds research notes (`reports/`, `research_notes/`) and no code. These owner files
  are untracked. All 13 tracked files are setup files.
- The layer is the full one: tier `long`, 15 skill links in `.claude/skills` and 15 in `.agents/skills`, a
  regression ledger, a test ratchet, `CODING_STANDARDS.md`, a UI rule, a Serena project file with no language, a
  pre-commit hook, an issue tracker doc. The Done section speaks of a verify skill and e2e tests.
- `.ai/docs-allow` lists the 5 owner notes as "allowed outside docs/". The notes are not in git.
- No remote. So the rules "draft PR", "the owner merges on GitHub" and the PR gate cannot apply. The adopt went
  to `main` through 2 local merge commits.
- An empty folder `advice.detachedHead=false/` was made on 2026-11-16 at 15:43, between `ai-start` (14:14) and the
  adopt commit (19:10). OMC project memory lists it as a main directory.
- `.omc/` holds 936 KB of state after 5 sessions.
- `.claude/settings.local.json` holds 23 allow rules from earlier sessions, some wide (`Bash(git *)`,
  `Bash(python3 *)`, `Bash(ssh *)`).

What is wrong: the layer does not fit the folder. A notes folder needs the global rules and the Markdown check.
It got everything, because the tier is fixed to `long`.

## 9. Adoption of a project that has its own AI setup

Short answer: `ai-adopt` is safe for the owner's files in most cases, and silent about each conflict. It has 2
defects that can publish work the owner did not want to publish. Section 12 has the results per fixture.

## 10. Risks

| Risk | Evidence | Size |
|---|---|---|
| A gate is skipped without a message on a slow machine | docs: timeout does not block; 2 router timeouts in one session | High |
| Commits and pushes blocked on a slow machine, agent sent to the owner | 7 of 7 secret-scan walls | High (stops work) |
| The agent says done with a red check | Stop check off on dev-mac | High (goal "checks its own work") |
| A rule of another plugin stops or steers the agent | OMC read budget, drift guard, memory, hints | Medium |
| The setup changes faster than it is tested | 14 PRs in 3 days, 9 regressions, no CI | Medium |
| One owner maintains 20,500 lines | size table | Medium |
| A new machine pays the full cost | 12 processes at session start, a 21 MB binary, 135 skills | Medium |
| The agent follows a stale statement | Makefile and rules say the Stop hook runs check-fast | Low |

## 11. Target shape

Three layers, each with one job.

1. **Text, short.** Only what a hook cannot check: reply shape, judgement, where knowledge lives. One reply-shape
   rule, not three. Target: under 100 lines of global rules.
2. **Git hooks for git rules.** One global hook that runs before the repo's own hooks. A research pass of the
   same day found that a global `core.hooksPath` alone does not work with husky and the pre-commit tool; see
   `docs/maps/setup-shape/issues/03-git-hooks-as-the-seam.md` for the open test. `pre-commit`: no commit on main or master, built-in secret scan on the staged diff, the
   verify commit gate, lint. `pre-push`: no push to main or master, secret scan on the pushed range (gitleaks
   may run here). These hooks hold for Claude, Codex, subagents, the shell and the owner. They need no parser of
   shell command text and they have no agent hook timeout.
3. **Agent hooks for the rest, narrow.** Each with an `if` filter and `onFailure: "block"`: `gh pr create, edit,
   ready, merge`; edits of `.env` files and of agent docs; the Skill winner gate; Stop (verify used, check-fast).
   Session start prints the status. Nothing runs on Read, Glob, Grep or Agent calls.

Removed: rules that fire on prompt words; the Stop check process where the profile turns it off; dead tier
code; OMC hooks on dev-mac (plugin off by default, on per project, as on the servers).

Expected process counts after the change: a Bash call that is not git or gh: 1 (RTK) in place of 7. A Read: 0
in place of 7. A Stop: 2 in place of 7.

## 12. Results of the adoption experiment

A subagent built 8 fixture repos in a temp folder and ran `ai-adopt --yes --no-onboard` on each, 2 times (agent;
command output kept in the temp folder). No fixture had a remote, so the push path was not run.

| Fixture | Exit | End branch | Second run changes nothing | `make check-fast` |
|---|---|---|---|---|
| Plain Python | 0 | `ai-adopt` | yes | 0 |
| Own AI setup, files tracked | 0 | `ai-adopt` | yes | 0 |
| Own AI setup, files untracked | 0 | `ai-adopt` | yes | 0 |
| husky | 0 | `ai-adopt` | yes | 0 |
| Own `.git/hooks/pre-commit` | 0 | `ai-adopt` | yes | 0 |
| Uncommitted work | 0 | `ai-adopt` | yes | 0 |
| Monorepo (2 packages) | 0 | `ai-adopt` | yes | **2: no `check-fast` target** |
| On a feature branch | 0 | the feature branch | yes | 0 |

One run took 541.6 s on the loaded machine; a fresh copy took 6.1 s. The slow run wrote "measured 45 s" into
the Map.

Defects, most serious first:

1. **Uncommitted edits go into the adopt commit.** WIP lines in `CLAUDE.md`, `Makefile` and `.gitignore` were
   committed with the message "adopt base AI setup v4". With a remote, the adopt also pushes.
2. **Files the owner keeps local get committed.** `CLAUDE.md`, `AGENTS.md` and `.claude/settings.json` were
   untracked and hidden by the owner's global git ignore. The adopt commit added them.
3. **graphify hooks land in the shared hook folder.** With husky, 4 untracked files of 13 to 16 KB appear in
   `.husky/` (`post-commit`, `post-checkout`, `post-merge`, `post-rewrite`). One `git add .husky` gives them to
   each teammate.
4. **No commit gate with own hooks.** With husky or an own pre-commit hook, `ai-precommit` is not called. The
   tool prints one "keep" line. `.pre-commit-config.yaml` is not named.
5. **On a feature branch the adopt commit mixes with the feature.**
6. **Uncommitted work moves to the branch `ai-adopt`.** It is not lost, and not stashed. A later run on `main`
   stops with "the branch ai-adopt exists, but the state of its PR is unknown", and the setup folders show as
   untracked there.
7. **Monorepo:** no check target is written, but the Done text still asks for `check-fast` green. Serena indexes
   one language only.
8. **Two `## Map` headings** when the project has a hand-written Map.
9. **Skill name clash:** a project folder `.claude/skills/tdd` is kept, but `.agents/skills/tdd` links to the
   shared skill. Claude and Codex then load 2 different `tdd` skills.
10. **`.claude/settings.json` is rewritten** (same keys, new format) and gets `enabledPlugins` and
    `skillOverrides`.
11. **The tree is dirty after the adopt** in Python repos without an ignore rule: `__pycache__/` from the test run.
12. **Each adopt adds a project entry to `~/.serena/serena_config.yml`.** The experiment left 8 entries for temp
    folders there (lines 264 to 271). They are not removed yet.

What the adopt does not report: rules in the project's `CLAUDE.md` that contradict the global rules ("Commit
directly to main", "Always write long detailed answers" stayed, with no message), a hook in the project's
settings, an MCP server in `.mcp.json`, Cursor rules, Copilot instructions.

What it keeps byte for byte: project commands, agents, own skills, `.mcp.json`, Cursor and Copilot files, the
`check` and `test` targets, the Done section (one verify line is added inside it).

The folder `advice.detachedHead=false` did not appear in any fixture. The string exists only in the installer
steps (`adapters/tools.sh`, `adapters/claude.sh`), which the experiment did not run.

## 13. Sources

- Claude Code hooks reference, https://code.claude.com/docs/en/hooks (`if`, `onFailure`, `async`, timeouts,
  parallel runs).
- Timing harness and process tables: commands run for this audit on 2026-11-18; the harness is not in the repo.
- Subagent reports (architecture walk, plugin inventory, adoption experiment) of the same session.
- Earlier findings: `docs/tickets/setup-audit/`.
