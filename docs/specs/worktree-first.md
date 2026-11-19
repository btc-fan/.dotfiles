# Spec: worktree-first

Status: agreed with the owner on 2026-11-19. Branch `worktree-first`.

## Problem Statement

The owner wants each job to run in its own git worktree, from main or master by default, or from the base the owner names. After the merge, the worktree and the branch must go.

An audit on 2026-11-19 found this:

1. "Make a branch before the first edit" was text only. No gate blocked an edit on main.
2. No rule said "a worktree for each job". Only `/implement-spec` used worktrees.
3. The cleanup note at session start named merged branches, but not the path of their worktrees.

## Solution

- Gate `worktree-first` (PreToolUse on Edit, Write, MultiEdit, NotebookEdit): it denies an agent edit of a file in an adopted repo (the repo has `.ai/`) when that checkout is on main or master. The message gives the command: `git -C <root> worktree add ../<repo>-<slug> -b <slug> origin/<main>`.
- These pass: a gitignored file (local state), a repo without `.ai/`, a file outside a repo, and every feature branch.
- The worktree path is the existing convention: `../<repo>-<slug>`, a folder beside the repo (owner: keep it flat).
- The `feature-grill` nudge starts with the worktree step.
- The `merge-review` session-start note names the worktree path of each merged branch: `git worktree remove <path>`, then `git branch -D`, then `git worktree prune`.
- The ship skill already removes the worktree and the branch after the merge.

## Out of Scope

- Shell writes (`sed -i`, `>`) and Codex `apply_patch` on main. A `shortcut:` comment in `hooklib.py` names this limit.
- A branch that was never pushed has no "gone" remote, so the note does not name it.

## Tests

`ai/tests/cases/worktree-first.json` (7 cases), `feature-grill.json` (the worktree step), `test_commands.py` (`t_merged_branches_note`: the worktree path).
