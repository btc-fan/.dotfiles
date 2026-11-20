# AI setup

The owner's shared rules, gates and skills for every AI agent on every machine and project.

## Risk and approval

**Low-risk work**:
Reads, tests, and local edits and commits in a worktree. An agent does it without a question.
_Avoid_: safe command, normal work

**High-impact step**:
A step that can stop a running service, change how a machine boots, reach other people, or destroy data. An agent shows the plan, the risk and the undo, then waits for the owner's OK.
_Avoid_: critical step, dangerous command, serious thing

**Live host**:
A machine with services that run for the owner. Each machine lists its live hosts in `~/.config/ai/live-hosts`.
_Avoid_: production host, server (when it means any machine)

**Typed OK**:
The owner's own typed "go", "ok" or "approve" for one shown plan. It does not cover a later step. A pasted or quoted "ok" is not a typed OK.
_Avoid_: approval (alone), permission, standing permission

**Prepare**:
An owner request to write the files and the plan only. It never covers a start, an enable, a deploy or a PR. "Plan" and "set up" mean the same.
_Avoid_: get ready, make it work
