# 01: Orchestrator mode for herdr sessions (backlog)

**What to build (later):** when the owner opens a Claude session through herdr, the session can work as an orchestrator: plan the work, hand each step to herdr agents, review their results and report. Today this is an idea only. Nothing is built.

**Blocked by:** owner decision (the 3 questions at the end)

**Status:** backlog (owner 2026-11-18: keep it, do not build it yet)

## The proposed prompt (from a friend of the owner, kept word for word)

```
You are the orchestrator. Plan the work, delegate each step to herdr (hc) agents,
review their results, and report to me. Do not do large code or verify work in your
own context.

Goal: <goal>.

How to delegate:
- Start each agent with:
  hc run --bg --name <short-name> --cwd <repo> env CLAUDE_CODE_AUTO_COMPACT_WINDOW=450000 claude "<task>"
- Put the task in a file ($TMPDIR/task-<name>.md) and tell the agent to read it.
- Each agent: keep tool output small, write a handoff file ($TMPDIR/handoff-<name>.md)
  at each milestone, and report back with `hc send <your-terminal-id> "<=60-word summary + handoff path>"`.
- Flow per step: code agent -> verify agent -> your review -> my "go" -> commit/push.
- Only one agent edits files at a time.
- Agents are read-only unless the task says otherwise.

Report to me in <=60 words. Wait for my "go" before any push.
```

## Audit (2026-11-18)

Herdr already ships the same idea as a template: `~/.config/herdr-core/templates/assistant.md` (the "Assistant": never writes code, splits the ask into tasks, starts one worker per task in its own git worktree with `herdr-task`, watches them, steps in when one is stuck), plus `worker.md` and `reviewer.md`. Herdr gives the Assistant text only to the Assistant tab. Its SessionStart hook (`~/.config/herdr-app/mods/chat/session-note.sh`) acts only when `HC_TERMINAL_ID` is set.

| Prompt line | herdr Assistant or worker | This setup |
|---|---|---|
| start agents with `hc run --bg ... claude` | start them only with `herdr-task`, never by hand | `claude -p` or `codex exec` (global AGENTS.md, "Other agents") |
| workers report with `hc send <id>` | workers do not report; herdr sends the Assistant their news | none |
| only one agent edits files at a time | parallel tasks, one worktree each (default 3 at once) | `/implement-spec`: one worktree per ticket, in parallel |
| wait for "go" before any push | the worker's `herdr-task ready` pushes its branch | standing permission: push the feature branch and a draft PR |
| handoff files in `$TMPDIR` | `herdr-task status` and `ready` | the `handoff` skill |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW=450000` | not used | not found in the Claude Code binary or docs: unconfirmed |
| report in 60 words or less; a verify agent per step | a proof artifact per task | the 60-word rule; the verify tool and its hooks |

Trap: herdr workers are herdr sessions too (`HC_TERMINAL_ID` is set). If every herdr session gets "you are the orchestrator, never write code", the workers refuse to code and delegate again. Only the coordinating session may get the orchestrator text.

## Proposal (not decided)

1. Use herdr's Assistant as the orchestrator, not a second prompt.
2. Make this setup and herdr agree. The router detects a herdr worker (label `herdr.task`) and the Assistant (label `herdr.coordinator`). In a worker, herdr's push, pull request and ready flow wins, and the "draft PR after the first ticket" rule stays quiet. The verify run's evidence feeds herdr's Proof step. The "Other agents" rule names `herdr-task` inside herdr.
3. Prove it with the verify tool: an Assistant session and a worker session, and check which text each one gets.

## Open questions for the owner

1. Use herdr's Assistant as the orchestrator, or the prompt above?
2. Inside herdr, does herdr's push and pull request flow win over this setup's rules?
3. Is `CLAUDE_CODE_AUTO_COMPACT_WINDOW` real? Check the Claude Code docs before any use.

- [ ] Owner answers the 3 questions
- [ ] Spec and tickets, then build
