# Verify tool and hooks: speed, and how the sources integrate it (2026-11-19)

Owner question: do the longer hook time limits (PR "hook timeouts") slow down development? What other ways
are there to make agents use the project verify tool? Research only. Nothing here is decided or built.

## Sources (the 4 links from the owner)

1. pstack generator, the original author: https://github.com/cursor/plugins/blob/main/pstack/skills/create-verification-skill/SKILL.md
2. Worked example (verify-atlas): https://github.com/poteto/verification-skill-example
3. A real project (kody): https://github.com/kody-hq/kody/blob/main/.agents/skills/control-kody/SKILL.md
4. PR system recap, not a code diff (kody): https://github.com/kody-hq/kody/blob/main/.agents/skills/visual-recap/SKILL.md

Links 1 to 3 are the most important for this setup.

## 1. Do the time limits slow work? No.

A hook `timeout` is an upper limit. A hook that ends fast returns at once
(https://code.claude.com/docs/en/hooks). Measured on the main Mac (load 4), router on this branch, 3 runs each:

| Event | Payload | Time |
|---|---|---|
| UserPromptSubmit | a normal prompt | 0.17 s |
| PreToolUse | `ls` | 0.16 s |
| PreToolUse | `git push` (secret scan) | 0.46 s |
| Stop | no code change | 0.18 to 0.30 s |

The old 5 s limit fired only while the machine load was 260. A longer limit matters only when the machine is
overloaded or a hook hangs.

Important: when Claude Code stops a PreToolUse hook at its limit, the hook gives no decision and the tool call
runs. So the hook limit (90 s) must stay above the scan budget (75 s). Then the router denies a slow scan
itself, and a push never goes out unscanned.

## 2. What the sources do

None of the 3 sources uses a hook to force the verify tool.

| Source | How the agent gets to the verify tool | Who checks the proof |
|---|---|---|
| pstack | The skill is typed by a person (`disable-model-invocation: true`). | One verifier agent per PR that did not write the code. It posts PASS, PASS+NOTES or FAIL on the PR. A verdict stays valid after a rebase while `git patch-id` is the same. |
| verify-atlas | The prompt says "use /verify-<app> ... show me a video and screenshots as proof". The feature playbook says "Inconclusive or wrong-surface is not a pass". | The PR has a fixed `## Verification` section. A person reads it. |
| kody | The model can start the skill ("Use when changing UI, account routes, preview deploys"). AGENTS.md says "Verify UI/API with control-kody first". | visual-recap sets a risk level from the diff (composes = low, extends = medium, adds = high). The risk level sets how much proof the PR needs. CI checks only that the feature map is current. |

Speed tricks in the sources:
- Use the app that runs now, or start it and wait for `/health` (kody `dev:ensure`; Atlas uses the running build).
- The doctor reports build freshness, so the agent knows if the running app has the change.
- Keep the login session (kody keeps a seed cookie).
- `verify <feature>` runs all checks of one feature file in one command.
- Load one feature file for one change, not all of them.
- Use API proof first, and the browser only when the change is in the UI.
- Wait for the page to settle, never `sleep`.

## 3. Claude Code options

| Option | Fit |
|---|---|
| `command` hook (what we have) | Fast (under 0.5 s). It can block. Keep it for the cheap checks. |
| `async: true` hook | Cannot block. Good for logs, not for gates. |
| `agent` hook on Stop | Starts a subagent (up to 50 tool turns) on each turn end. Too slow and costly for each turn. |
| A `verifier` subagent in `.claude/agents/` with `skills: [verify-<app>]` | Native. The subagent drives the app in its own context, so the main context stays small. The verify skill must stay model-invocable to be preloaded. |
| Skill `context: fork` | The skill runs in a subagent without the chat history. Good for a self-contained verify run. |
| `if: "Bash(git push *)"` on a PreToolUse hook | The hook process starts only for matching commands. Today the router starts on each Bash call (0.16 s). |

## 4. Options for this setup (owner decides)

1. Keep the 4 hooks and make the verify tool cheap: `ensure` (reuse the running app), a doctor with build
   freshness, session reuse, `verify <feature>` for one feature file. Lowest risk. The hooks stay, the run gets
   faster.
2. Add a `verifier` subagent that preloads `verify-<app>`. The ship skill starts it once per PR. It did not
   write the code, and it writes the run log and a PASS, PASS+NOTES or FAIL verdict. This copies the pstack
   verifier.
3. Move the strict check from each turn end (hook 2) to the PR (hook 4), scaled by risk as visual-recap does:
   a docs or config PR needs no drive, and a new route needs a full drive. Fewer blocks while the agent works.
   The cost: problems show later, at the PR.

Recommended order: 1, then 2. Option 3 makes the enforcement weaker, so it waits for the 7-day wall review
(ticket 17 of verify-enforcement).
